"""
Sample Repository Extraction & Validation

Extracts PL/SQL from the plsql-sample-code repo and validates it.
"""

import json
import os
import re
from typing import Dict, List, Any, Optional
from pathlib import Path


class PlSqlExtractor:
    """Extracts PL/SQL objects from .pks and .pkb files"""
    
    def __init__(self):
        self.packages = {}
    
    def extract_from_file(self, file_path: str, file_type: str) -> Optional[Dict[str, Any]]:
        """
        Extract PL/SQL object from .pks or .pkb file
        
        Args:
            file_path: Path to .pks or .pkb file
            file_type: "SPEC" or "BODY"
            
        Returns:
            Extracted package object
        """
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return self.extract_from_content(content, file_type, file_path)
    
    def extract_from_content(self, content: str, file_type: str, source: str) -> Dict[str, Any]:
        """Extract from content string"""
        
        # Extract package name
        pkg_name_match = re.search(r'(?:CREATE\s+)?PACKAGE\s+(?:BODY\s+)?(\w+)', content, re.IGNORECASE)
        pkg_name = pkg_name_match.group(1) if pkg_name_match else "unknown"
        
        return {
            "name": pkg_name,
            "type": f"PACKAGE_{file_type}",
            "source": content,
            "source_file": source,
            "file_type": file_type,
            
            # Analyze content
            "exceptions": self._extract_exceptions(content),
            "cursor_count": self._count_cursors(content),
            "retry_count": self._count_retries(content),
            "dml_count": self._count_dml(content),
            "tables_used": self._extract_tables(content),
            "procedures": self._extract_procedures(content),
            "functions": self._extract_functions(content),
            "error_handling": self._extract_error_handling(content),
        }
    
    def _extract_exceptions(self, content: str) -> List[str]:
        """Extract exception handlers"""
        exceptions = []
        
        # Look for EXCEPTION keyword
        if re.search(r'\bEXCEPTION\b', content, re.IGNORECASE):
            exceptions.append("CUSTOM_EXCEPTION")
        
        # Look for specific exception types
        if re.search(r'\bNO_DATA_FOUND\b', content, re.IGNORECASE):
            exceptions.append("NO_DATA_FOUND")
        if re.search(r'\bTOO_MANY_ROWS\b', content, re.IGNORECASE):
            exceptions.append("TOO_MANY_ROWS")
        if re.search(r'\bVALUE_ERROR\b', content, re.IGNORECASE):
            exceptions.append("VALUE_ERROR")
        
        return exceptions
    
    def _count_cursors(self, content: str) -> int:
        """Count cursor declarations"""
        count = 0
        count += len(re.findall(r'\bCURSOR\b', content, re.IGNORECASE))
        if re.search(r'\bSELECT\b.*\bFROM\b', content, re.IGNORECASE):
            count += 1
        return count
    
    def _count_retries(self, content: str) -> int:
        """Count retry loops"""
        count = 0
        count += len(re.findall(r'\bLOOP\b', content, re.IGNORECASE))
        count += len(re.findall(r'\bGOTO\b', content, re.IGNORECASE))
        return count
    
    def _count_dml(self, content: str) -> int:
        """Count DML statements"""
        count = 0
        count += len(re.findall(r'\bINSERT\b', content, re.IGNORECASE))
        count += len(re.findall(r'\bUPDATE\b', content, re.IGNORECASE))
        count += len(re.findall(r'\bDELETE\b', content, re.IGNORECASE))
        return count
    
    def _extract_tables(self, content: str) -> List[str]:
        """Extract table names from DML"""
        tables = []
        
        # Simple pattern for INSERT INTO table_name, UPDATE table_name, DELETE FROM table_name
        patterns = [
            r'INSERT\s+INTO\s+(\w+)',
            r'UPDATE\s+(\w+)',
            r'DELETE\s+FROM\s+(\w+)',
            r'FROM\s+(\w+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            tables.extend(matches)
        
        # Remove duplicates
        return list(set(tables))
    
    def _extract_procedures(self, content: str) -> List[str]:
        """Extract procedure names"""
        procs = re.findall(r'PROCEDURE\s+(\w+)', content, re.IGNORECASE)
        return list(set(procs))
    
    def _extract_functions(self, content: str) -> List[str]:
        """Extract function names"""
        funcs = re.findall(r'FUNCTION\s+(\w+)', content, re.IGNORECASE)
        return list(set(funcs))
    
    def _extract_error_handling(self, content: str) -> str:
        """Determine error handling approach"""
        if re.search(r'RAISE\s+\w+_ERROR', content, re.IGNORECASE):
            return "RAISE_ERROR"
        elif re.search(r'EXCEPTION\b', content, re.IGNORECASE):
            return "EXCEPTION_HANDLING"
        elif re.search(r'raise_application_error', content, re.IGNORECASE):
            return "RAISE_APPLICATION_ERROR"
        else:
            return "IMPLICIT"


def extract_repository(repo_path: str) -> Dict[str, Any]:
    """
    Extract all PL/SQL files from repository
    
    Args:
        repo_path: Path to repository with .pks and .pkb files
        
    Returns:
        Extraction result with packages
    """
    extractor = PlSqlExtractor()
    packages = []
    
    # Find all .pks and .pkb files
    repo_dir = Path(repo_path)
    pks_files = list(repo_dir.glob("**/*.pks"))
    pkb_files = list(repo_dir.glob("**/*.pkb"))
    
    print(f"Found {len(pks_files)} .pks files and {len(pkb_files)} .pkb files")
    
    # Extract specs
    for pks_file in pks_files:
        pkg = extractor.extract_from_file(str(pks_file), "SPEC")
        if pkg:
            packages.append(pkg)
            print(f"  Extracted: {pkg['name']} (SPEC) from {pks_file.name}")
    
    # Extract bodies
    for pkb_file in pkb_files:
        pkg = extractor.extract_from_file(str(pkb_file), "BODY")
        if pkg:
            packages.append(pkg)
            print(f"  Extracted: {pkg['name']} (BODY) from {pkb_file.name}")
    
    return {
        "analysis_scope": "REPOSITORY",
        "packages": packages,
        "file_count": len(pks_files) + len(pkb_files),
        "timestamp": "2024"
    }


if __name__ == "__main__":
    # Example: Extract from a local repository
    sample_repo = r"c:\projects\plsql_Accelerator\plsql_sample_repo"
    
    if os.path.exists(sample_repo):
        print("Extracting from sample repository...")
        result = extract_repository(sample_repo)
        
        print(f"\nExtraction complete: {len(result['packages'])} packages")
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Repository not found: {sample_repo}")
