"""
FastAPI backend for the PL/SQL modernization pipeline.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from main import PLSQLModernizationPipeline
from src.parser.discovery_analyzer import analyze_sql_source
from src.parser.sql_table_discovery import SQLDiscoveryParseError, extract_create_table_names


def _utc_now() -> str:
    """Return an ISO timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    """Represents a frontend conversion job."""

    job_id: str
    source_type: str
    source_value: str
    config_path: str
    config_overrides: Optional[Dict[str, Any]] = None
    output_directory: Optional[str] = None
    status: str = "queued"
    created_at: str = field(default_factory=_utc_now)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class GitConversionRequest(BaseModel):
    """Request body for a git-based conversion job."""

    repo_url: str = Field(..., min_length=1)
    config_path: str = "config.json"
    config_overrides: Optional[Dict[str, Any]] = None
    output_directory: Optional[str] = None


class DatabaseConversionRequest(BaseModel):
    """Request body for a database-based conversion job."""

    connection_string: str = Field(..., min_length=1)
    config_path: str = "config.json"
    config_overrides: Optional[Dict[str, Any]] = None
    output_directory: Optional[str] = None


class FilePathConversionRequest(BaseModel):
    """Request body for a server-local file or directory conversion job."""

    source_path: str = Field(..., min_length=1)
    config_path: str = "config.json"
    config_overrides: Optional[Dict[str, Any]] = None
    output_directory: Optional[str] = None


class OracleConnectionRequest(BaseModel):
    """Structured Oracle connection details for metadata APIs."""

    host: str = Field(..., min_length=1)
    port: int = Field(default=1521, ge=1, le=65535)
    service_name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class OracleObjectsRequest(OracleConnectionRequest):
    """Request model for listing Oracle objects."""

    schema_name: str = Field(..., min_length=1)
    object_types: List[str] = Field(
        default_factory=lambda: ["PROCEDURE", "FUNCTION", "PACKAGE", "TRIGGER"]
    )


class OracleConvertRequest(OracleConnectionRequest):
    """Request model for creating a conversion job from structured Oracle credentials."""

    config_path: str = "config.json"
    config_overrides: Optional[Dict[str, Any]] = None
    output_directory: Optional[str] = None


class GitTableDiscoveryRequest(BaseModel):
    """Request body for git SQL table discovery."""

    repo_url: str = Field(..., min_length=1)
    branch: Optional[str] = None
    path_filters: List[str] = Field(default_factory=list)


class GitRepoTreeRequest(BaseModel):
    """Request body for git repo tree browsing."""

    repo_url: str = Field(..., min_length=1)
    branch: Optional[str] = None
    path: Optional[str] = None


class DiscoveryAnalyzeRequest(BaseModel):
    """Request body for discovery metadata analysis."""

    file_id: Optional[str] = None
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    path_filters: List[str] = Field(default_factory=list)


DISCOVERY_FILE_EXTENSIONS = {".sql", ".pks", ".pkb", ".pls", ".prc", ".fnc"}
SYSTEM_SCHEMAS = {
    "SYS",
    "SYSTEM",
    "XDB",
    "OUTLN",
    "DBSNMP",
    "APPQOSSYS",
    "AUDSYS",
    "GSMADMIN_INTERNAL",
    "SYSBACKUP",
    "SYSDG",
    "SYSKM",
    "SYSRAC",
}
CREATE_OBJECT_PATTERN = re.compile(
    r"\bcreate\s+(?:or\s+replace\s+)?(?:editionable\s+|noneditionable\s+)?(procedure|function|package(?:\s+body)?)\b",
    flags=re.IGNORECASE,
)


def _is_valid_repo_url(repo_url: str) -> bool:
    """Return True when repo_url looks like an HTTPS/SSH git URL."""
    if repo_url.startswith("git@"):
        return True
    parsed = urlparse(repo_url)
    return parsed.scheme in {"http", "https", "ssh", "git"} and bool(parsed.netloc)


def _decode_text_content(content: bytes) -> str:
    """Decode bytes to text using UTF-8 first and a permissive fallback."""
    if b"\x00" in content:
        raise ValueError("Uploaded content appears to be a binary file")

    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode text content")


def _parse_config_overrides(raw_value: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse config override JSON from form or query payloads."""
    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("config_overrides must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("config_overrides must be a JSON object")
    return parsed


def _normalize_filter_prefix(path_filter: str) -> str:
    """Normalize a path filter for prefix matching."""
    return path_filter.replace("\\", "/").strip().lstrip("./").rstrip("/")


def _path_matches_filters(path: Path, repo_root: Path, path_filters: List[str]) -> bool:
    """Return True when a file path matches requested repo path prefixes."""
    if not path_filters:
        return True
    relative_path = path.relative_to(repo_root).as_posix()
    normalized_filters = [_normalize_filter_prefix(item) for item in path_filters if item.strip()]
    if not normalized_filters:
        return True
    return any(
        relative_path == prefix or relative_path.startswith(f"{prefix}/") for prefix in normalized_filters
    )


def _discover_tables_from_git(request: GitTableDiscoveryRequest) -> Dict[str, Any]:
    """Clone a repository and discover CREATE TABLE names from supported SQL file types."""
    if not _is_valid_repo_url(request.repo_url):
        raise ValueError("Invalid repo_url. Use an HTTPS or SSH git URL.")

    try:
        import git
    except ImportError as exc:
        raise RuntimeError("GitPython is required for git discovery endpoint") from exc

    temp_root = Path(tempfile.gettempdir()) / "plsql_acc_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="discovery_", dir=temp_root) as temp_dir:
        repo_dir = Path(temp_dir) / "repo"
        clone_kwargs: Dict[str, Any] = {"depth": 1, "single_branch": True}
        if request.branch:
            clone_kwargs["branch"] = request.branch

        try:
            git.Repo.clone_from(request.repo_url, str(repo_dir), **clone_kwargs)
        except git.exc.GitCommandError as exc:
            error_text = str(exc).lower()
            if any(token in error_text for token in ("not found", "repository", "remote branch", "pathspec")):
                raise FileNotFoundError(f"Repository or branch not found: {request.repo_url}") from exc
            raise RuntimeError(f"Failed to clone repository: {exc}") from exc

        target_files = [
            file_path
            for file_path in repo_dir.rglob("*")
            if file_path.is_file()
            and file_path.suffix.lower() in DISCOVERY_FILE_EXTENSIONS
            and _path_matches_filters(file_path, repo_dir, request.path_filters)
        ]
        if request.path_filters and not target_files:
            raise FileNotFoundError("No matching files found for the supplied path_filters")

        discovered_tables = set()
        parse_errors: List[str] = []
        for file_path in target_files:
            try:
                sql_text = _decode_text_content(file_path.read_bytes())
                discovered_tables.update(extract_create_table_names(sql_text))
            except SQLDiscoveryParseError as exc:
                parse_errors.append(f"{file_path.name}: {exc}")
            except Exception as exc:
                parse_errors.append(f"{file_path.name}: {exc}")

        if parse_errors:
            raise SQLDiscoveryParseError("; ".join(parse_errors[:5]))

        tables = sorted(discovered_tables)
    return {
        "tables": tables,
        "files_scanned": len(target_files),
        "count": len(tables),
    }


def _list_git_tree(request: GitRepoTreeRequest) -> Dict[str, Any]:
    """Clone a repo and return the immediate children for a path."""
    if not _is_valid_repo_url(request.repo_url):
        raise ValueError("Invalid repo_url. Use an HTTPS or SSH git URL.")

    try:
        import git
    except ImportError as exc:
        raise RuntimeError("GitPython is required for git tree endpoint") from exc

    temp_root = Path(tempfile.gettempdir()) / "plsql_acc_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tree_", dir=temp_root) as temp_dir:
        repo_dir = Path(temp_dir) / "repo"
        clone_kwargs: Dict[str, Any] = {"depth": 1, "single_branch": True}
        if request.branch:
            clone_kwargs["branch"] = request.branch

        try:
            git.Repo.clone_from(request.repo_url, str(repo_dir), **clone_kwargs)
        except git.exc.GitCommandError as exc:
            error_text = str(exc).lower()
            if any(token in error_text for token in ("not found", "repository", "remote branch", "pathspec")):
                raise FileNotFoundError(f"Repository or branch not found: {request.repo_url}") from exc
            raise RuntimeError(f"Failed to clone repository: {exc}") from exc

        rel_path = (request.path or "").strip().lstrip("/").lstrip("./")
        target = (repo_dir / rel_path).resolve() if rel_path else repo_dir
        if not target.exists():
            raise FileNotFoundError("Requested path not found in repository")
        if target.is_file():
            target = target.parent

        entries = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            entries.append(
                {
                    "name": item.name,
                    "path": item.relative_to(repo_dir).as_posix(),
                    "type": "dir" if item.is_dir() else "file",
                }
            )

        return {
            "path": rel_path,
            "entries": entries,
            "count": len(entries),
        }


def _build_oracle_connection_string(request: OracleConnectionRequest) -> str:
    """Build an Oracle URI accepted by the existing pipeline."""
    return (
        f"oracle://{request.username}:{request.password}"
        f"@{request.host}:{request.port}/{request.service_name}"
    )


def _mask_connection_string(connection_string: str) -> str:
    """Hide credentials before returning job metadata to the client."""
    if "://" not in connection_string or "@" not in connection_string:
        return connection_string
    scheme, remainder = connection_string.split("://", 1)
    _, location = remainder.split("@", 1)
    return f"{scheme}://***:***@{location}"


class OracleMetadataService:
    """Oracle metadata helper used by the frontend APIs."""

    def __init__(self):
        try:
            import oracledb
        except ImportError as exc:
            raise RuntimeError("oracledb package is required for Oracle metadata APIs") from exc
        self.oracledb = oracledb

    def _connect(self, request: OracleConnectionRequest):
        """Create a thin Oracle connection."""
        dsn = self.oracledb.makedsn(request.host, request.port, service_name=request.service_name)
        return self.oracledb.connect(user=request.username, password=request.password, dsn=dsn)

    def _set_container(self, cursor, container: Optional[str]) -> None:
        """Switch to a selected PDB/container for metadata queries."""
        if not container:
            return
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_$#]*", container):
            raise ValueError("Invalid container name")
        cursor.execute(f"ALTER SESSION SET CONTAINER = {container}")

    def _raise_metadata_error(self, context: str, exc: Exception) -> None:
        """Raise consistent metadata errors with permission-sensitive hints."""
        message = str(exc)
        if "ORA-01031" in message or "insufficient privileges" in message.lower():
            raise PermissionError(f"{context}: insufficient privileges") from exc
        raise RuntimeError(f"{context}: {message}") from exc

    def test_connection(self, request: OracleConnectionRequest) -> Dict[str, Any]:
        """Open a connection and return basic database identity."""
        with self._connect(request) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        SYS_CONTEXT('USERENV', 'DB_NAME'),
                        SYS_CONTEXT('USERENV', 'CON_NAME'),
                        SYS_CONTEXT('USERENV', 'SERVICE_NAME'),
                        USER
                    FROM dual
                    """
                )
                db_name, con_name, service_name, current_user = cursor.fetchone()
        return {
            "connected": True,
            "db_name": db_name,
            "container_name": con_name,
            "service_name": service_name,
            "current_user": current_user,
        }

    def list_schemas(self, request: OracleConnectionRequest) -> Dict[str, Any]:
        """List schemas visible to the connected user."""
        with self._connect(request) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT username FROM all_users ORDER BY username")
                schemas = [row[0] for row in cursor.fetchall()]
        return {"schemas": schemas, "count": len(schemas)}

    def list_objects(self, request: OracleObjectsRequest) -> Dict[str, Any]:
        """List PL/SQL objects for a schema."""
        requested_types = [item.upper() for item in request.object_types if item]
        bind_names = []
        bind_values: Dict[str, Any] = {"owner": request.schema_name.upper()}
        for index, object_type in enumerate(requested_types):
            key = f"type_{index}"
            bind_names.append(f":{key}")
            bind_values[key] = object_type

        sql = f"""
            SELECT owner, object_name, object_type, status
            FROM all_objects
            WHERE owner = :owner
              AND object_type IN ({', '.join(bind_names)})
            ORDER BY object_type, object_name
        """
        with self._connect(request) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, bind_values)
                objects = [
                    {
                        "schema": row[0],
                        "name": row[1],
                        "type": row[2],
                        "status": row[3],
                    }
                    for row in cursor.fetchall()
                ]
        return {
            "schema": request.schema_name.upper(),
            "object_types": requested_types,
            "count": len(objects),
            "objects": objects,
        }

    def list_databases(self, request: OracleConnectionRequest) -> Dict[str, Any]:
        """Return current DB identity and accessible PDB/container metadata when available."""
        with self._connect(request) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        SYS_CONTEXT('USERENV', 'DB_NAME'),
                        SYS_CONTEXT('USERENV', 'CON_NAME'),
                        SYS_CONTEXT('USERENV', 'SERVICE_NAME')
                    FROM dual
                    """
                )
                db_name, con_name, service_name = cursor.fetchone()

                pdbs: List[Dict[str, Any]] = []
                try:
                    cursor.execute("SELECT name, open_mode FROM v$pdbs ORDER BY name")
                    pdbs = [{"name": row[0], "open_mode": row[1]} for row in cursor.fetchall()]
                except Exception:
                    pdbs = []

        return {
            "current_database": {
                "db_name": db_name,
                "container_name": con_name,
                "service_name": service_name,
            },
            "accessible_pdbs": pdbs,
            "count": len(pdbs),
            "note": (
                "This endpoint returns the current Oracle database plus accessible pluggable databases "
                "when the connected user has permission to query them."
            ),
        }

    def get_containers(self, request: OracleConnectionRequest) -> Dict[str, Any]:
        """List Oracle containers (PDBs when connected to a CDB, otherwise current DB)."""
        with self._connect(request) as connection:
            with connection.cursor() as cursor:
                try:
                    cursor.execute("SELECT CDB FROM V$DATABASE")
                    cdb_value = cursor.fetchone()[0]
                except Exception as exc:
                    self._raise_metadata_error("Failed to check CDB mode", exc)

                is_cdb = str(cdb_value).upper() == "YES"
                if is_cdb:
                    try:
                        cursor.execute(
                            """
                            SELECT NAME, OPEN_MODE
                            FROM V$PDBS
                            WHERE NAME <> 'PDB$SEED'
                            ORDER BY NAME
                            """
                        )
                        rows = cursor.fetchall()
                    except Exception as exc:
                        self._raise_metadata_error("Failed to list PDB containers", exc)

                    containers = [{"name": row[0], "type": "PDB", "openMode": row[1]} for row in rows]
                else:
                    try:
                        cursor.execute("SELECT NAME FROM V$DATABASE")
                        db_name = cursor.fetchone()[0]
                    except Exception as exc:
                        self._raise_metadata_error("Failed to read current database name", exc)
                    containers = [{"name": db_name, "type": "CDB"}]

        return {"containers": containers, "count": len(containers)}

    def get_schemas(self, request: OracleConnectionRequest, container: Optional[str]) -> Dict[str, Any]:
        """List user schemas in a selected container, excluding system users."""
        with self._connect(request) as connection:
            with connection.cursor() as cursor:
                try:
                    self._set_container(cursor, container)
                except Exception as exc:
                    self._raise_metadata_error("Failed to switch Oracle container", exc)

                try:
                    cursor.execute(
                        """
                        SELECT USERNAME
                        FROM ALL_USERS
                        WHERE ACCOUNT_STATUS = 'OPEN'
                        ORDER BY USERNAME
                        """
                    )
                except Exception:
                    # ALL_USERS may not expose ACCOUNT_STATUS in some Oracle setups.
                    cursor.execute("SELECT USERNAME FROM ALL_USERS ORDER BY USERNAME")
                rows = cursor.fetchall()

        schemas = [row[0] for row in rows if row[0] and row[0].upper() not in SYSTEM_SCHEMAS]
        return {"schemas": schemas, "count": len(schemas)}

    def get_objects(
        self,
        request: OracleConnectionRequest,
        schema: str,
        container: Optional[str],
    ) -> Dict[str, Any]:
        """List procedures/functions/packages/triggers in a schema."""
        normalized_schema = schema.upper()
        with self._connect(request) as connection:
            with connection.cursor() as cursor:
                try:
                    self._set_container(cursor, container)
                except Exception as exc:
                    self._raise_metadata_error("Failed to switch Oracle container", exc)

                try:
                    cursor.execute(
                        """
                        SELECT OBJECT_NAME, OBJECT_TYPE
                        FROM ALL_OBJECTS
                        WHERE OWNER = :schema
                          AND OBJECT_TYPE IN ('PROCEDURE', 'FUNCTION', 'PACKAGE', 'TRIGGER')
                        ORDER BY OBJECT_TYPE, OBJECT_NAME
                        """,
                        {"schema": normalized_schema},
                    )
                    rows = cursor.fetchall()
                except Exception as exc:
                    self._raise_metadata_error("Failed to list schema objects", exc)

        objects = [{"name": row[0], "type": row[1], "schema": normalized_schema} for row in rows]
        return {"objects": objects, "count": len(objects)}

    def _resolve_object_type(
        self,
        cursor,
        schema: str,
        object_name: str,
    ) -> str:
        """Verify the object exists and return its object_type."""
        cursor.execute(
            """
            SELECT OBJECT_TYPE
            FROM ALL_OBJECTS
            WHERE OWNER = :schema
              AND OBJECT_NAME = :name
              AND OBJECT_TYPE IN ('PROCEDURE', 'FUNCTION', 'PACKAGE', 'TRIGGER')
            """,
            {"schema": schema.upper(), "name": object_name.upper()},
        )
        row = cursor.fetchone()
        if not row:
            raise FileNotFoundError(f"{schema}.{object_name} not found in Oracle metadata")
        return row[0]

    def _fetch_ddl_from_metadata(
        self,
        cursor,
        object_type: str,
        schema: str,
        object_name: str,
    ) -> Optional[str]:
        """Return CREATE DDL via DBMS_METADATA or None when unavailable."""
        try:
            cursor.execute(
                "SELECT DBMS_METADATA.GET_DDL(:object_type, :object_name, :owner) FROM dual",
                {
                    "object_type": object_type,
                    "object_name": object_name.upper(),
                    "owner": schema.upper(),
                },
            )
            row = cursor.fetchone()
            ddl_value = row[0] if row else None
            if ddl_value is None:
                return None
            if hasattr(ddl_value, "read"):
                return ddl_value.read()
            return str(ddl_value)
        except self.oracledb.DatabaseError as exc:
            message = str(exc).lower()
            if "ora-01031" in message or "insufficient privileges" in message:
                raise PermissionError(
                    f"Insufficient privileges to fetch DDL for {schema}.{object_name}"
                ) from exc
            return None

    def _fetch_source_from_all_source(
        self,
        cursor,
        schema: str,
        object_name: str,
    ) -> str:
        cursor.execute(
            """
            SELECT TEXT
            FROM ALL_SOURCE
            WHERE OWNER = :owner
              AND NAME = :name
            ORDER BY LINE
            """,
            {"owner": schema.upper(), "name": object_name.upper()},
        )
        rows = [row[0] or "" for row in cursor.fetchall()]
        if not rows:
            raise FileNotFoundError(f"Source not found for {schema}.{object_name}")
        return "".join(rows)

    def _build_object_ddl(
        self,
        cursor,
        schema: str,
        object_name: str,
        object_type: str,
    ) -> str:
        parts: List[str] = []
        primary = self._fetch_ddl_from_metadata(cursor, object_type, schema, object_name)
        if primary:
            parts.append(primary)
        if object_type.upper() == "PACKAGE":
            body = self._fetch_ddl_from_metadata(cursor, "PACKAGE BODY", schema, object_name)
            if body:
                parts.append(body)
        if parts:
            return "\n\n".join(parts)
        return self._fetch_source_from_all_source(cursor, schema, object_name)

    def get_object_analysis(
        self,
        request: OracleConnectionRequest,
        schema: str,
        object_name: str,
        container: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze a live Oracle object and return discovery metadata."""
        normalized_schema = schema.upper()
        normalized_name = object_name.upper()
        with self._connect(request) as connection:
            with connection.cursor() as cursor:
                try:
                    self._set_container(cursor, container)
                except Exception as exc:
                    self._raise_metadata_error("Failed to switch Oracle container", exc)

                object_type = self._resolve_object_type(cursor, normalized_schema, normalized_name)
                ddl_text = self._build_object_ddl(cursor, normalized_schema, normalized_name, object_type)

        if not ddl_text.strip():
            raise FileNotFoundError(f"No source returned for {schema}.{object_name}")

        analysis_source = ddl_text
        normalized_ddl = ddl_text.strip().lower()
        if not CREATE_OBJECT_PATTERN.search(ddl_text):
            header_type = object_type.upper()
            if header_type == "PACKAGE" and re.search(r"\bpackage\s+body\b", ddl_text, flags=re.IGNORECASE):
                header_type = "PACKAGE BODY"
            analysis_source = (
                f"CREATE OR REPLACE {header_type} {normalized_schema}.{normalized_name}\n{ddl_text}"
            )
        elif not normalized_ddl.startswith("create"):
            analysis_source = f"CREATE OR REPLACE {object_type.upper()} {normalized_schema}.{normalized_name}\n{ddl_text}"

        analyses = analyze_sql_source(analysis_source)
        matches = [
            entry
            for entry in analyses
            if entry.get("procedureName", "").upper() == normalized_name
        ]

        if matches:
            analysis = dict(matches[0])
        elif analyses:
            analysis = dict(analyses[0])
            analysis["procedureName"] = normalized_name
            analysis["objectType"] = object_type
        else:
            analysis = {
                "procedureName": normalized_name,
                "objectType": object_type,
                "parameters": {"in": [], "out": []},
                "tablesUsed": [],
                "operations": [],
                "localVariables": [],
                "exceptions": [],
                "complexity": {
                    "linesOfCode": len([line for line in analysis_source.splitlines() if line.strip()]),
                    "numberOfQueries": 0,
                    "numberOfConditions": 0,
                    "numberOfLoops": 0,
                },
                "dependencyGraph": {"tablesUsed": [], "proceduresCalled": []},
                "conversionPreview": {
                    "entities": [],
                    "repositories": [],
                    "services": [],
                    "controllers": [],
                    "dtos": [],
                },
            }
        analysis["schema"] = normalized_schema
        analysis["container"] = container
        analysis["sourceSql"] = analysis_source
        return analysis


class JobManager:
    """Tracks API jobs and runs the modernization pipeline asynchronously."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, JobRecord] = {}
        self.tasks: Dict[str, asyncio.Task] = {}

    def create_job(
        self,
        source_type: str,
        source_value: str,
        config_path: str,
        config_overrides: Optional[Dict[str, Any]] = None,
        output_directory: Optional[str] = None,
    ) -> JobRecord:
        """Register a new job before execution."""
        job_id = uuid4().hex
        job = JobRecord(
            job_id=job_id,
            source_type=source_type,
            source_value=source_value,
            config_path=config_path,
            config_overrides=config_overrides,
            output_directory=output_directory,
        )
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> JobRecord:
        """Fetch an existing job or raise a 404-style error."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job

    def get_job_dir(self, job_id: str) -> Path:
        """Return the filesystem root for a job."""
        return self.root_dir / job_id

    def get_output_dir(self, job_id: str) -> Path:
        """Return the per-job output directory."""
        job = self.get_job(job_id)
        if job.output_directory:
            return Path(job.output_directory)
        return self.get_job_dir(job_id) / "output"

    async def run_job(
        self,
        job_id: str,
        source_path: str,
        source_type: str,
        config_path: str,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Execute the modernization pipeline for a job."""
        job = self.get_job(job_id)
        output_dir = self.get_output_dir(job_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        job.status = "running"
        job.started_at = _utc_now()
        try:
            pipeline = PLSQLModernizationPipeline(
                config_path=config_path,
                output_directory=str(output_dir),
                config_overrides=config_overrides,
            )
            result = await pipeline.run_pipeline(source_path, source_type)
            job.status = "completed"
            job.result = result
            job.completed_at = _utc_now()
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = _utc_now()

    def start_job(self, job: JobRecord, source_path: str) -> None:
        """Start a job in the current event loop."""
        task = asyncio.create_task(
            self.run_job(
                job_id=job.job_id,
                source_path=source_path,
                source_type=job.source_type,
                config_path=job.config_path,
                config_overrides=job.config_overrides,
            )
        )
        self.tasks[job.job_id] = task

    def serialize_job(self, job: JobRecord) -> Dict[str, Any]:
        """Convert a job record into JSON-ready data."""
        payload = asdict(job)
        if job.source_type == "database":
            payload["source_value"] = _mask_connection_string(job.source_value)
        payload["output_directory"] = str(self.get_output_dir(job.job_id))
        payload["download_url"] = (
            f"/api/jobs/{job.job_id}/download" if job.status == "completed" and job.result else None
        )
        payload["files_url"] = (
            f"/api/jobs/{job.job_id}/files" if job.status == "completed" and job.result else None
        )
        return payload


@dataclass
class DiscoveryUploadRecord:
    """Represents an uploaded source file for discovery APIs."""

    file_id: str
    filename: str
    path: str
    size: int
    created_at: str = field(default_factory=_utc_now)


class DiscoveryManager:
    """Stores uploaded discovery files and latest object-level analyses."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.uploads: Dict[str, DiscoveryUploadRecord] = {}
        self.by_procedure: Dict[str, Dict[str, Any]] = {}

    def save_upload(self, source_file: UploadFile, content: bytes) -> DiscoveryUploadRecord:
        file_id = uuid4().hex
        safe_name = Path(source_file.filename or "uploaded.sql").name
        destination = self.root_dir / f"{file_id}_{safe_name}"
        destination.write_bytes(content)
        record = DiscoveryUploadRecord(
            file_id=file_id,
            filename=safe_name,
            path=str(destination),
            size=len(content),
        )
        self.uploads[file_id] = record
        return record

    def get_upload(self, file_id: str) -> DiscoveryUploadRecord:
        record = self.uploads.get(file_id)
        if not record:
            raise KeyError(file_id)
        return record

    def store_analyses(self, analyses: List[Dict[str, Any]]) -> None:
        for item in analyses:
            name = item.get("procedureName")
            if not name:
                continue
            self.by_procedure[name.upper()] = item

    def get_analysis(self, procedure_name: str) -> Dict[str, Any]:
        item = self.by_procedure.get(procedure_name.upper())
        if not item:
            raise KeyError(procedure_name)
        return item


class OracleConnectionStore:
    """In-memory connection context from the connect step for discovery GET endpoints."""

    def __init__(self):
        self._current: Optional[OracleConnectionRequest] = None
        self._schema: Optional[str] = None
        self._container: Optional[str] = None

    def set(self, request: OracleConnectionRequest) -> None:
        self._current = request

    def get(self) -> OracleConnectionRequest:
        if not self._current:
            raise KeyError("Oracle connection context not set")
        return self._current

    def set_schema_context(self, schema: Optional[str], container: Optional[str] = None) -> None:
        """Remember the last schema/container used for discovery details."""
        self._schema = schema.upper() if schema else None
        if container is not None:
            self._container = container

    def get_schema(self) -> Optional[str]:
        return self._schema

    def get_container(self) -> Optional[str]:
        return self._container


app = FastAPI(
    title="PL/SQL Modernization Backend",
    version="1.0.0",
    description="Backend API for converting PL/SQL sources to Spring Boot projects.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_manager = JobManager(Path.cwd() / ".api_jobs")
oracle_metadata_service = OracleMetadataService()
discovery_manager = DiscoveryManager(Path.cwd() / ".api_jobs" / "discovery_uploads")
oracle_connection_store = OracleConnectionStore()


@app.get("/health")
async def health() -> Dict[str, str]:
    """Basic health check."""
    return {"status": "ok"}


def _pick_directory() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError("Tkinter is required for folder picker") from exc
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    selected = filedialog.askdirectory()
    root.destroy()
    return selected or None


@app.get("/api/paths/pick-directory")
async def pick_directory() -> Dict[str, Optional[str]]:
    """Open a local folder picker on the backend host and return the selected path."""
    try:
        path = await asyncio.to_thread(_pick_directory)
        return {"path": path}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/discovery/upload")
async def upload_discovery_file(source_file: Optional[UploadFile] = File(None)) -> Dict[str, Any]:
    """Upload a SQL/PLSQL source file for discovery analysis."""
    if not source_file:
        raise HTTPException(status_code=400, detail="Missing source_file")

    try:
        content = await source_file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Invalid file: empty upload")
        _decode_text_content(content)
        record = discovery_manager.save_upload(source_file, content)
        return {
            "file_id": record.file_id,
            "filename": record.filename,
            "size": record.size,
            "created_at": record.created_at,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


def _collect_git_sql_text(request: DiscoveryAnalyzeRequest) -> str:
    """Clone a repo and concatenate SQL-like files for discovery analysis."""
    if not request.repo_url or not _is_valid_repo_url(request.repo_url):
        raise ValueError("Invalid repo_url. Use an HTTPS or SSH git URL.")

    try:
        import git
    except ImportError as exc:
        raise RuntimeError("GitPython is required for git discovery endpoint") from exc

    temp_root = Path(tempfile.gettempdir()) / "plsql_acc_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="discovery_", dir=temp_root) as temp_dir:
        repo_dir = Path(temp_dir) / "repo"
        clone_kwargs: Dict[str, Any] = {"depth": 1, "single_branch": True}
        if request.branch:
            clone_kwargs["branch"] = request.branch

        try:
            git.Repo.clone_from(request.repo_url, str(repo_dir), **clone_kwargs)
        except git.exc.GitCommandError as exc:
            error_text = str(exc).lower()
            if any(token in error_text for token in ("not found", "repository", "remote branch", "pathspec")):
                raise FileNotFoundError(f"Repository or branch not found: {request.repo_url}") from exc
            raise RuntimeError(f"Failed to clone repository: {exc}") from exc

        target_files = [
            file_path
            for file_path in repo_dir.rglob("*")
            if file_path.is_file()
            and file_path.suffix.lower() in DISCOVERY_FILE_EXTENSIONS
            and _path_matches_filters(file_path, repo_dir, request.path_filters)
        ]
        if request.path_filters and not target_files:
            raise FileNotFoundError("No matching files found for the supplied path_filters")
        if not target_files:
            raise FileNotFoundError("No SQL/PLSQL files found in repository")

        chunks: List[str] = []
        parse_errors: List[str] = []
        for file_path in target_files:
            try:
                text = _decode_text_content(file_path.read_bytes())
                chunks.append(text)
            except Exception as exc:
                parse_errors.append(f"{file_path.name}: {exc}")
        if parse_errors:
            raise SQLDiscoveryParseError("; ".join(parse_errors[:5]))
        return "\n\n".join(chunks)


@app.post("/api/discovery/analyze")
async def analyze_discovery_source(request: DiscoveryAnalyzeRequest) -> Dict[str, Any]:
    """Analyze uploaded SQL source (or git SQL sources) and return object-level metadata."""
    try:
        if request.file_id:
            upload = discovery_manager.get_upload(request.file_id)
            sql_text = _decode_text_content(Path(upload.path).read_bytes())
            source_kind = "upload"
        elif request.repo_url:
            sql_text = await asyncio.to_thread(_collect_git_sql_text, request)
            source_kind = "git"
        else:
            raise HTTPException(status_code=400, detail="Provide either file_id or repo_url")

        analyses = analyze_sql_source(sql_text)
        if not analyses:
            raise HTTPException(status_code=422, detail="No PROCEDURE/FUNCTION/PACKAGE objects found")
        discovery_manager.store_analyses(analyses)

        primary = analyses[0]
        return {
            **primary,
            "objects": analyses,
            "count": len(analyses),
            "source": source_kind,
        }
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Uploaded file not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLDiscoveryParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


@app.get("/api/discovery/containers")
async def discovery_containers() -> Dict[str, Any]:
    """List Oracle containers for the current connection context."""
    try:
        request = oracle_connection_store.get()
        return await asyncio.to_thread(oracle_metadata_service.get_containers, request)
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail="Connect step is required before discovery. Call /api/db/oracle/test-connection first.",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list containers: {exc}") from exc


@app.get("/api/discovery/schemas")
async def discovery_schemas(container: Optional[str] = Query(None)) -> Dict[str, Any]:
    """List user schemas in the selected Oracle container."""
    try:
        request = oracle_connection_store.get()
        return await asyncio.to_thread(oracle_metadata_service.get_schemas, request, container)
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail="Connect step is required before discovery. Call /api/db/oracle/test-connection first.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list schemas: {exc}") from exc


@app.get("/api/discovery/objects")
async def discovery_objects(
    schema: str = Query(..., min_length=1),
    container: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """List PL/SQL objects in the selected schema."""
    try:
        request = oracle_connection_store.get()
        result = await asyncio.to_thread(oracle_metadata_service.get_objects, request, schema, container)
        oracle_connection_store.set_schema_context(schema, container)
        return result
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail="Connect step is required before discovery. Call /api/db/oracle/test-connection first.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list objects: {exc}") from exc


@app.get("/api/discovery/{procedure_name}")
async def get_discovery_details(
    procedure_name: str,
    schema: Optional[str] = Query(None, min_length=1),
    container: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Return cached discovery details for a procedure/function/package or fetch the data from Oracle.
    """
    try:
        return discovery_manager.get_analysis(procedure_name)
    except KeyError:
        pass

    try:
        request = oracle_connection_store.get()
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail="Connect step is required before discovery. Call /api/db/oracle/test-connection first.",
        ) from exc

    schema_name = schema or oracle_connection_store.get_schema() or request.username
    if not schema_name:
        raise HTTPException(status_code=400, detail="Schema name is required to fetch discovery details.")

    container_name = container or oracle_connection_store.get_container()
    oracle_connection_store.set_schema_context(schema_name, container_name)

    try:
        analysis = await asyncio.to_thread(
            oracle_metadata_service.get_object_analysis,
            request,
            schema_name,
            procedure_name,
            container_name,
        )
        discovery_manager.store_analyses([analysis])
        return analysis
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve discovery details: {exc}") from exc


@app.post("/api/discovery/sql-file/tables")
async def discover_tables_from_sql_file(source_file: Optional[UploadFile] = File(None)) -> Dict[str, Any]:
    """Discover CREATE TABLE names from a user-uploaded SQL file."""
    if not source_file:
        raise HTTPException(status_code=400, detail="Missing source_file")

    try:
        content = await source_file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Invalid file: empty upload")
        sql_text = _decode_text_content(content)
        tables = extract_create_table_names(sql_text)
        return {"tables": tables, "count": len(tables)}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLDiscoveryParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


@app.post("/api/discovery/git/tables")
async def discover_tables_from_git(request: GitTableDiscoveryRequest) -> Dict[str, Any]:
    """Discover CREATE TABLE names from supported SQL-like files in a git repository."""
    try:
        return await asyncio.to_thread(_discover_tables_from_git, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLDiscoveryParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


@app.post("/api/discovery/git/tree")
async def list_git_tree(request: GitRepoTreeRequest) -> Dict[str, Any]:
    """List folders/files for a git repository path."""
    try:
        return await asyncio.to_thread(_list_git_tree, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


@app.post("/api/jobs/file")
async def create_file_job(
    source_file: UploadFile = File(...),
    config_path: str = Form("config.json"),
    config_overrides: Optional[str] = Form(None),
    output_directory: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Create a job from an uploaded local SQL/PLSQL file."""
    try:
        overrides = _parse_config_overrides(config_overrides)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job = job_manager.create_job("file", source_file.filename, config_path, overrides, output_directory)
    input_dir = job_manager.get_job_dir(job.job_id) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    saved_path = input_dir / (source_file.filename or "uploaded.sql")
    saved_path.write_bytes(await source_file.read())
    job_manager.start_job(job, str(saved_path))
    return job_manager.serialize_job(job)


@app.post("/api/jobs/file-path")
async def create_file_path_job(request: FilePathConversionRequest) -> Dict[str, Any]:
    """Create a job from a server-local file or directory path."""
    job = job_manager.create_job(
        "file",
        request.source_path,
        request.config_path,
        request.config_overrides,
        request.output_directory,
    )
    job_manager.start_job(job, request.source_path)
    return job_manager.serialize_job(job)


@app.post("/api/jobs/git")
async def create_git_job(request: GitConversionRequest) -> Dict[str, Any]:
    """Create a job from a git repository URL."""
    job = job_manager.create_job(
        "git",
        request.repo_url,
        request.config_path,
        request.config_overrides,
        request.output_directory,
    )
    job_manager.start_job(job, request.repo_url)
    return job_manager.serialize_job(job)


@app.post("/api/jobs/database")
async def create_database_job(request: DatabaseConversionRequest) -> Dict[str, Any]:
    """Create a job from an Oracle connection string."""
    job = job_manager.create_job(
        "database",
        request.connection_string,
        request.config_path,
        request.config_overrides,
        request.output_directory,
    )
    job_manager.start_job(job, request.connection_string)
    return job_manager.serialize_job(job)


@app.post("/api/db/oracle/convert")
async def create_oracle_conversion_job(request: OracleConvertRequest) -> Dict[str, Any]:
    """Create a conversion job from structured Oracle connection details."""
    connection_string = _build_oracle_connection_string(request)
    job = job_manager.create_job(
        "database",
        connection_string,
        request.config_path,
        request.config_overrides,
        request.output_directory,
    )
    job_manager.start_job(job, connection_string)
    return job_manager.serialize_job(job)


@app.post("/api/db/oracle/test-connection")
async def test_oracle_connection(request: OracleConnectionRequest) -> Dict[str, Any]:
    """Verify Oracle connectivity and return basic database identity."""
    try:
        response = await asyncio.to_thread(oracle_metadata_service.test_connection, request)
        oracle_connection_store.set(request)
        return response
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Oracle connection failed: {exc}") from exc


@app.post("/api/db/oracle/schemas")
async def list_oracle_schemas(request: OracleConnectionRequest) -> Dict[str, Any]:
    """List schemas visible to the Oracle user."""
    try:
        return await asyncio.to_thread(oracle_metadata_service.list_schemas, request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to list schemas: {exc}") from exc


@app.post("/api/db/oracle/objects")
async def list_oracle_objects(request: OracleObjectsRequest) -> Dict[str, Any]:
    """List PL/SQL objects for a schema."""
    try:
        return await asyncio.to_thread(oracle_metadata_service.list_objects, request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to list objects: {exc}") from exc


@app.post("/api/db/oracle/databases")
async def list_oracle_databases(request: OracleConnectionRequest) -> Dict[str, Any]:
    """Return current database and accessible pluggable databases metadata."""
    try:
        return await asyncio.to_thread(oracle_metadata_service.list_databases, request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to list databases: {exc}") from exc


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> Dict[str, Any]:
    """Return the current status of a job."""
    try:
        job = job_manager.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    return job_manager.serialize_job(job)


@app.get("/api/jobs/{job_id}/files")
async def list_job_files(job_id: str) -> Dict[str, Any]:
    """List generated files for a completed job."""
    try:
        job = job_manager.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    return {
        "job_id": job_id,
        "output_directory": str(job_manager.get_output_dir(job_id)),
        "files": job.result.get("generated_files", []),
    }


@app.get("/api/jobs/{job_id}/file-content")
async def get_job_file_content(job_id: str, path: str = Query(..., min_length=1)) -> Dict[str, Any]:
    """Return text content for a generated file."""
    try:
        job = job_manager.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=409, detail="Job has not completed yet")

    output_dir = job_manager.get_output_dir(job_id).resolve()
    requested_path = (output_dir / path).resolve()
    if output_dir not in requested_path.parents and requested_path != output_dir:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not requested_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "job_id": job_id,
        "path": path,
        "content": requested_path.read_text(encoding="utf-8", errors="ignore"),
    }


@app.get("/api/jobs/{job_id}/download")
async def download_job_output(job_id: str) -> FileResponse:
    """Download the generated output for a completed job as a zip archive."""
    try:
        job = job_manager.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=409, detail="Job has not completed yet")

    output_dir = job_manager.get_output_dir(job_id)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")

    archive_base = job_manager.get_job_dir(job_id) / "generated-output"
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=output_dir))
    return FileResponse(
        path=archive_path,
        media_type="application/zip",
        filename=f"{job_id}.zip",
    )
