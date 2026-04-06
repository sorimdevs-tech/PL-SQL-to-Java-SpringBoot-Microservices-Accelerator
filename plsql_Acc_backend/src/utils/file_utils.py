"""
File utilities for PL/SQL Modernization Platform
Handles extraction of PL/SQL code from various sources
"""

import os
import re
import asyncio
import tempfile
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator
from urllib.parse import quote, urlparse, urlunparse
import logging
from dataclasses import dataclass
from datetime import datetime

# Import platform utilities
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class PLSQLFile:
    """Represents a PL/SQL file with metadata"""
    filename: str
    content: str
    file_type: str  # procedure, function, trigger, package, anonymous
    database_object_name: Optional[str] = None
    schema: Optional[str] = None


class FileExtractor:
    """Extracts PL/SQL code from various sources"""
    
    def __init__(self):
        """Initialize file extractor"""
        self.supported_extensions = {
            '.sql', '.pls', '.pkb', '.pks', '.pkg', '.pck', '.plb', '.prc', '.fnc', '.trg'
        }
        self.ignored_directories = {
            '.git', '.hg', '.svn', '.venv', 'venv',
            'node_modules', 'dist', 'build', 'target', '.idea', '.vscode',
        }
        self.plsql_keywords = {
            'procedure', 'function', 'trigger', 'package', 'type', 
            'cursor', 'exception', 'pragma', 'declare', 'begin', 'end'
        }
        self._git_repo_counter = 0
        self._enable_git_long_paths()
        self.plsql_strong_patterns = [
            re.compile(
                r"\bcreate\s+(?:or\s+replace\s+)?(?:editionable\s+|noneditionable\s+)?"
                r"(?:package(?:\s+body)?|procedure|function|trigger|type(?:\s+body)?)\b",
                flags=re.IGNORECASE,
            ),
            re.compile(r"\bpragma\s+autonomous_transaction\b", flags=re.IGNORECASE),
            re.compile(r"\braise_application_error\s*\(", flags=re.IGNORECASE),
            re.compile(r"\bdeclare\b[\s\S]{0,1200}\bbegin\b", flags=re.IGNORECASE),
        ]
    
    def _enable_git_long_paths(self):
        """Enable git long paths support on Windows to handle deep directory structures"""
        import subprocess
        import sys
        
        if sys.platform == 'win32':
            try:
                # Enable long paths globally for git
                subprocess.run(['git', 'config', '--global', 'core.longpaths', 'true'], 
                             capture_output=True, timeout=5)
                logger.info("Git long paths support enabled")
            except Exception as e:
                logger.warning(f"Could not enable git long paths support: {e}")
    
    def extract_from_file(self, file_path: str) -> Dict[str, str]:
        """
        Extract PL/SQL code from a single file or directory
        
        Args:
            file_path (str): Path to file or directory
            
        Returns:
            Dict[str, str]: Dictionary of filename -> content
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File or directory not found: {file_path}")
        
        if path.is_file():
            return {path.name: self._read_file(path)}
        else:
            return self._extract_from_directory(path)
    
    def _read_file(self, file_path: Path) -> str:
        """
        Read file content with proper encoding handling
        
        Args:
            file_path (Path): Path to file
            
        Returns:
            str: File content
        """
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                logger.debug(f"Successfully read {file_path} with encoding {encoding}")
                return content
            except UnicodeDecodeError:
                continue
        
        raise ValueError(f"Unable to decode file {file_path} with any of the attempted encodings")
    
    def _extract_from_directory(self, directory_path: Path) -> Dict[str, str]:
        """
        Extract PL/SQL files from directory recursively
        
        Args:
            directory_path (Path): Path to directory
            
        Returns:
            Dict[str, str]: Dictionary of filename -> content
        """
        files_content: Dict[str, str] = {}

        for root, dirs, files in os.walk(directory_path):
            dirs[:] = [d for d in dirs if d not in self.ignored_directories]
            root_path = Path(root)
            for file_name in files:
                file_path = root_path / file_name
                if not self._is_plsql_file(file_path):
                    continue
                try:
                    content = self._read_file(file_path)
                    relative_key = file_path.relative_to(directory_path).as_posix()
                    dedup_key = relative_key
                    suffix = 2
                    while dedup_key in files_content:
                        dedup_key = f"{relative_key}#{suffix}"
                        suffix += 1
                    files_content[dedup_key] = content
                    logger.debug(f"Extracted PL/SQL file: {dedup_key}")
                except Exception as e:
                    logger.warning(f"Failed to read file {file_path}: {e}")
        
        logger.info(f"Extracted {len(files_content)} PL/SQL files from directory")
        return files_content
    
    def _is_plsql_file(self, file_path: Path) -> bool:
        """
        Check if file is a PL/SQL file
        
        Args:
            file_path (Path): Path to file
            
        Returns:
            bool: True if PL/SQL file
        """
        if any(part in self.ignored_directories for part in file_path.parts):
            return False

        if file_path.suffix.lower() in self.supported_extensions:
            return True
        
        # For unknown extensions, require stronger PL/SQL evidence to avoid
        # shell/git hook scripts being misclassified.
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(8001)
                if not content.strip():
                    return False

                matched_strong = any(pattern.search(content) for pattern in self.plsql_strong_patterns)
                if matched_strong:
                    return True

                content_lower = content.lower()
                keyword_hits = sum(1 for keyword in self.plsql_keywords if keyword in content_lower)
                return keyword_hits >= 4 and ('begin' in content_lower and 'end' in content_lower)
        except:
            return False
    
    async def extract_from_git(self, repo_url: str, branch: str = "main") -> Dict[str, str]:
        """
        Extract PL/SQL code from Git repository
        
        Args:
            repo_url (str): Git repository URL
            branch (str): Branch to clone (default: main)
            
        Returns:
            Dict[str, str]: Dictionary of filename -> content
        """
        try:
            import git
        except ImportError:
            raise ImportError("GitPython is required for Git repository extraction. Install with: pip install GitPython")
        
        # Use a workspace-local temp directory with shorter names to avoid Windows path length limits
        temp_root = Path.cwd() / ".tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self._git_repo_counter += 1
        temp_dir = temp_root / f"r{self._git_repo_counter}"
        
        # Clean up directory if it exists from a previous failed attempt
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug(f"Cleaned up existing temporary directory: {temp_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up existing directory {temp_dir}: {cleanup_error}")
        
        try:
            logger.info(f"Cloning repository: {repo_url}")
            try:
                git.Repo.clone_from(repo_url, str(temp_dir), branch=branch)
            except Exception as clone_error:
                # Some repos still use a non-main default branch (e.g., master).
                if "Remote branch" in str(clone_error) and "not found" in str(clone_error):
                    logger.warning(
                        f"Branch '{branch}' not found for {repo_url}. Retrying with repository default branch."
                    )
                    git.Repo.clone_from(repo_url, str(temp_dir))
                else:
                    raise
            logger.info(f"Repository cloned successfully to {temp_dir}")
            
            # Extract files from cloned repository
            return self._extract_from_directory(temp_dir)
            
        except Exception as e:
            logger.error(f"Failed to clone repository {repo_url}: {e}")
            raise
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean temporary repository directory {temp_dir}: {cleanup_error}")
    
    async def extract_from_database(self, connection_string: str, 
                                  schemas: Optional[List[str]] = None,
                                  object_types: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Extract PL/SQL code from Oracle database
        
        Args:
            connection_string (str): Database connection string
            schemas (Optional[List[str]]): List of schemas to extract from
            object_types (Optional[List[str]]): List of object types to extract
            
        Returns:
            Dict[str, str]: Dictionary of object_name -> source_code
        """
        try:
            import cx_Oracle
        except ImportError:
            raise ImportError("cx_Oracle is required for database extraction. Install with: pip install cx-Oracle")
        
        # Parse connection string
        parsed = urlparse(connection_string)
        if parsed.scheme != 'oracle':
            raise ValueError("Connection string must use oracle:// scheme")
        
        # Build connection parameters
        dsn = cx_Oracle.makedsn(parsed.hostname, parsed.port, service_name=parsed.path.lstrip('/'))
        username = parsed.username
        password = parsed.password
        
        if not username or not password:
            raise ValueError("Username and password required in connection string")
        
        try:
            # Connect to database
            connection = cx_Oracle.connect(username, password, dsn)
            logger.info(f"Connected to Oracle database: {parsed.hostname}")
            
            # Build query
            query = self._build_source_query(schemas, object_types)
            
            # Execute query
            with connection.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
            
            # Group results by object
            objects = {}
            for name, type_, line, text in results:
                key = f"{name}.{type_}"
                if key not in objects:
                    objects[key] = []
                objects[key].append((line, text))
            
            # Reconstruct source code
            source_code = {}
            for key, lines in objects.items():
                # Sort by line number and join
                sorted_lines = sorted(lines, key=lambda x: x[0])
                content = ''.join(line_text for _, line_text in sorted_lines)
                source_code[key] = content
            
            logger.info(f"Extracted {len(source_code)} PL/SQL objects from database")
            return source_code
            
        except Exception as e:
            logger.error(f"Failed to extract from database: {e}")
            raise
        finally:
            if 'connection' in locals():
                connection.close()
    
    def _build_source_query(self, schemas: Optional[List[str]], 
                          object_types: Optional[List[str]]) -> str:
        """
        Build SQL query to extract PL/SQL source from database
        
        Args:
            schemas (Optional[List[str]]): List of schemas
            object_types (Optional[List[str]]): List of object types
            
        Returns:
            str: SQL query
        """
        query = """
        SELECT name, type, line, text
        FROM all_source
        WHERE 1=1
        """
        
        conditions = []
        
        if schemas:
            schema_list = "', '".join(schemas)
            conditions.append(f"owner IN ('{schema_list}')")
        
        if object_types:
            type_list = "', '".join(object_types)
            conditions.append(f"type IN ('{type_list}')")
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY name, type, line"
        
        return query
    
    def categorize_plsql_objects(self, files_content: Dict[str, str]) -> Dict[str, List[PLSQLFile]]:
        """
        Categorize PL/SQL files by object type
        
        Args:
            files_content (Dict[str, str]): Dictionary of filename -> content
            
        Returns:
            Dict[str, List[PLSQLFile]]: Categorized PL/SQL objects
        """
        categorized = {
            'procedures': [],
            'functions': [],
            'triggers': [],
            'packages': [],
            'types': [],
            'anonymous_blocks': []
        }
        
        for filename, content in files_content.items():
            try:
                plsql_file = self._analyze_plsql_file(filename, content)
                if plsql_file.file_type in categorized:
                    categorized[plsql_file.file_type].append(plsql_file)
                else:
                    categorized['anonymous_blocks'].append(plsql_file)
            except Exception as e:
                logger.warning(f"Failed to analyze file {filename}: {e}")
                # Treat as anonymous block if analysis fails
                categorized['anonymous_blocks'].append(PLSQLFile(
                    filename=filename,
                    content=content,
                    file_type='anonymous',
                    database_object_name=None
                ))
        
        return categorized
    
    def _analyze_plsql_file(self, filename: str, content: str) -> PLSQLFile:
        """
        Analyze PL/SQL file to determine object type and metadata
        
        Args:
            filename (str): Name of the file
            content (str): Content of the file
            
        Returns:
            PLSQLFile: Analyzed PL/SQL file
        """
        content_upper = content.upper().strip()
        
        # Check for package specification
        if re.search(r'\bPACKAGE\s+\w+', content_upper):
            file_type = 'packages'
            object_name = self._extract_object_name(content, r'PACKAGE\s+(\w+)')
        # Check for package body
        elif re.search(r'\bPACKAGE\s+BODY\s+\w+', content_upper):
            file_type = 'packages'
            object_name = self._extract_object_name(content, r'PACKAGE\s+BODY\s+(\w+)')
        # Check for procedure
        elif re.search(r'\bPROCEDURE\s+\w+', content_upper):
            file_type = 'procedures'
            object_name = self._extract_object_name(content, r'PROCEDURE\s+(\w+)')
        # Check for function
        elif re.search(r'\bFUNCTION\s+\w+', content_upper):
            file_type = 'functions'
            object_name = self._extract_object_name(content, r'FUNCTION\s+(\w+)')
        # Check for trigger
        elif re.search(r'\bTRIGGER\s+\w+', content_upper):
            file_type = 'triggers'
            object_name = self._extract_object_name(content, r'TRIGGER\s+(\w+)')
        # Check for type
        elif re.search(r'\bTYPE\s+\w+\s+IS\s+OBJECT', content_upper):
            file_type = 'types'
            object_name = self._extract_object_name(content, r'TYPE\s+(\w+)\s+IS\s+OBJECT')
        else:
            file_type = 'anonymous'
            object_name = None
        
        return PLSQLFile(
            filename=filename,
            content=content,
            file_type=file_type,
            database_object_name=object_name
        )
    
    def _extract_object_name(self, content: str, pattern: str) -> Optional[str]:
        """
        Extract object name using regex pattern
        
        Args:
            content (str): PL/SQL content
            pattern (str): Regex pattern to match
            
        Returns:
            Optional[str]: Extracted object name
        """
        match = re.search(pattern, content, re.IGNORECASE)
        return match.group(1) if match else None
    
    def validate_plsql_syntax(self, content: str) -> bool:
        """
        Basic validation of PL/SQL syntax
        
        Args:
            content (str): PL/SQL content to validate
            
        Returns:
            bool: True if syntax appears valid
        """
        # Basic checks
        content = content.strip()
        
        # Check for balanced BEGIN/END
        begin_count = content.upper().count('BEGIN')
        end_count = content.upper().count('END')
        
        if begin_count != end_count:
            logger.warning("Unbalanced BEGIN/END blocks detected")
            return False
        
        # Check for proper termination
        if not content.endswith(';') and not content.endswith('/'):
            logger.warning("PL/SQL block may not be properly terminated")
            return False
        
        return True
    
    def extract_sql_queries(self, content: str) -> List[str]:
        """
        Extract SQL queries from PL/SQL content
        
        Args:
            content (str): PL/SQL content
            
        Returns:
            List[str]: List of SQL queries
        """
        # Pattern to match SQL statements
        sql_patterns = [
            r'SELECT\s+.*?FROM\s+.*?;',
            r'INSERT\s+INTO\s+.*?;',
            r'UPDATE\s+.*?SET\s+.*?;',
            r'DELETE\s+FROM\s+.*?;',
            r'MERGE\s+INTO\s+.*?;',
        ]
        
        queries = []
        for pattern in sql_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            queries.extend(matches)
        
        # Clean up queries
        cleaned_queries = []
        for query in queries:
            # Remove extra whitespace and newlines
            cleaned = re.sub(r'\s+', ' ', query.strip())
            cleaned_queries.append(cleaned)
        
        return cleaned_queries
    
    def extract_table_references(self, content: str) -> List[str]:
        """
        Extract table references from PL/SQL content
        
        Args:
            content (str): PL/SQL content
            
        Returns:
            List[str]: List of table names
        """
        # Pattern to match table references
        table_patterns = [
            r'FROM\s+([A-Z_][A-Z0-9_]*\.?[A-Z_][A-Z0-9_]*)',
            r'INTO\s+([A-Z_][A-Z0-9_]*\.?[A-Z_][A-Z0-9_]*)',
            r'UPDATE\s+([A-Z_][A-Z0-9_]*\.?[A-Z_][A-Z0-9_]*)',
            r'JOIN\s+([A-Z_][A-Z0-9_]*\.?[A-Z_][A-Z0-9_]*)',
        ]
        
        tables = set()
        for pattern in table_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                # Remove schema prefix if present
                table_name = match.split('.')[-1]
                if table_name and len(table_name) > 1:  # Filter out single letters
                    tables.add(table_name.upper())
        
        return list(tables)


class GitRepoPublisher:
    """Publishes generated output into a Git repository."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or Path.cwd())

    async def publish_directory(
        self,
        source_dir: str | Path,
        repo_url: str,
        branch: Optional[str] = None,
        base_branch: Optional[str] = None,
        target_subdirectory: Optional[str] = None,
        access_token: Optional[str] = None,
        username: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> Dict[str, str | bool]:
        """
        Clone a target repository, copy generated files into it, commit, and push.

        Args:
            source_dir: Generated local output directory.
            repo_url: Target Git repository URL or path.
            branch: Branch to publish to. Defaults to the repository's active/default branch.
            base_branch: Existing branch used as the starting point when creating a new branch.
            target_subdirectory: Optional relative subdirectory inside the repo.
            access_token: Optional PAT for HTTPS repositories.
            username: Optional username for token auth. Defaults to x-access-token.
            commit_message: Optional commit message.
        """
        source_path = Path(source_dir)
        if not source_path.exists() or not source_path.is_dir():
            raise FileNotFoundError(f"Generated output directory not found: {source_path}")

        try:
            import git
            from git import Actor
        except ImportError as exc:
            raise ImportError(
                "GitPython is required for Git repository publishing. Install with: pip install GitPython"
            ) from exc

        temp_root = self.workspace_root / ".tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self._git_repo_counter += 1
        temp_dir = temp_root / f"p{self._git_repo_counter}"
        
        # Clean up directory if it exists from a previous failed attempt
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug(f"Cleaned up existing temporary directory: {temp_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up existing directory {temp_dir}: {cleanup_error}")
        
        auth_repo_url = self._build_authenticated_repo_url(repo_url, access_token, username)

        try:
            logger.info("Cloning output target repository: %s", repo_url)
            repo = git.Repo.clone_from(auth_repo_url, str(temp_dir))
            active_branch = self._checkout_branch(repo, branch, base_branch)
            destination_root = temp_dir / self._normalize_target_subdirectory(target_subdirectory)
            destination_root.mkdir(parents=True, exist_ok=True)

            self._copy_directory_contents(source_path, destination_root)

            repo.git.add(A=True)
            if not repo.is_dirty(untracked_files=True):
                logger.info("No changes detected while publishing output to %s", repo_url)
                return {
                    "published": False,
                    "repo_url": repo_url,
                    "branch": active_branch,
                    "target_path": self._display_target_path(target_subdirectory),
                    "message": "No changes to publish.",
                }

            author_name = os.getenv("GIT_AUTHOR_NAME", "PLSQL Accelerator")
            author_email = os.getenv("GIT_AUTHOR_EMAIL", "plsql-accelerator@example.com")
            actor = Actor(author_name, author_email)
            message = commit_message or f"Add generated output from PL/SQL Accelerator ({datetime.utcnow().date().isoformat()})"
            commit = repo.index.commit(message, author=actor, committer=actor)
            repo.remotes.origin.push(f"HEAD:{active_branch}")

            logger.info("Published generated output to %s on branch %s", repo_url, active_branch)
            return {
                "published": True,
                "repo_url": repo_url,
                "branch": active_branch,
                "target_path": self._display_target_path(target_subdirectory),
                "commit_message": message,
                "commit_hash": commit.hexsha,
            }
        except Exception as exc:
            logger.error("Failed to publish generated output to %s: %s", repo_url, exc)
            raise
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _checkout_branch(self, repo, branch: Optional[str], base_branch: Optional[str] = None) -> str:
        """Check out the requested branch, creating it from the chosen base branch if necessary."""
        if not branch:
            try:
                return repo.active_branch.name
            except TypeError:
                return "HEAD"

        remote_branch_names = {ref.remote_head for ref in repo.remotes.origin.refs}
        local_branch_names = {head.name for head in repo.heads}

        if branch in local_branch_names:
            repo.git.checkout(branch)
        elif branch in remote_branch_names:
            repo.git.checkout("-b", branch, f"origin/{branch}")
        else:
            normalized_base_branch = (base_branch or "").strip()
            if normalized_base_branch and normalized_base_branch != branch:
                if normalized_base_branch in local_branch_names:
                    repo.git.checkout(normalized_base_branch)
                elif normalized_base_branch in remote_branch_names:
                    repo.git.checkout("-b", normalized_base_branch, f"origin/{normalized_base_branch}")
                else:
                    raise ValueError(f"Base branch not found in target repository: {normalized_base_branch}")
            repo.git.checkout("-b", branch)
        return branch

    def _normalize_target_subdirectory(self, target_subdirectory: Optional[str]) -> Path:
        """Return a safe relative target directory inside the repo."""
        if not target_subdirectory:
            return Path(".")

        normalized = target_subdirectory.replace("\\", "/").strip().strip("/")
        if not normalized:
            return Path(".")

        candidate = Path(normalized)
        if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
            raise ValueError("github_output.target_path must stay inside the target repository")
        return candidate

    def _display_target_path(self, target_subdirectory: Optional[str]) -> str:
        normalized = self._normalize_target_subdirectory(target_subdirectory)
        return "." if normalized == Path(".") else normalized.as_posix()

    def _copy_directory_contents(self, source_dir: Path, destination_dir: Path) -> None:
        """Copy all generated files into the requested repository location."""
        for item in source_dir.iterdir():
            destination = destination_dir / item.name
            if item.is_dir():
                if destination.exists() and destination.is_file():
                    destination.unlink()
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and destination.is_dir():
                    shutil.rmtree(destination)
                shutil.copy2(item, destination)

    def _build_authenticated_repo_url(
        self,
        repo_url: str,
        access_token: Optional[str] = None,
        username: Optional[str] = None,
    ) -> str:
        """Inject token credentials for HTTPS remotes when provided."""
        if not access_token:
            return repo_url

        parsed = urlparse(repo_url)
        if parsed.scheme not in {"http", "https"}:
            logger.warning("Ignoring access token because repo URL is not HTTP(S): %s", repo_url)
            return repo_url

        credential_user = quote(username or "x-access-token", safe="")
        credential_token = quote(access_token, safe="")
        hostname = parsed.hostname or ""
        if parsed.port:
            hostname = f"{hostname}:{parsed.port}"
        netloc = f"{credential_user}:{credential_token}@{hostname}"
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
