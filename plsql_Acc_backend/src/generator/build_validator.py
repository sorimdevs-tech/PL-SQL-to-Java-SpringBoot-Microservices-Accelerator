"""
Build Validation System - Maven/Gradle Compilation Testing

This module provides build validation capabilities:
1. Compile generated Spring Boot projects
2. Detect Java compilation errors
3. Provide feedback for LLM repair
4. Support both Maven and Gradle builds
"""

import subprocess
import os
import sys
import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import tempfile
import shutil

logger = logging.getLogger(__name__)


@dataclass
class CompilationError:
    """Represents a Java compilation error"""
    file: str  # Filename where error occurred
    line: int  # Line number
    column: int  # Column number
    message: str  # Error message
    code: str  # Error code (e.g., "cannot find symbol")
    
    def __str__(self):
        return f"{self.file}:{self.line}:{self.column}: {self.code} - {self.message}"


@dataclass
class BuildResult:
    """Result of a build attempt"""
    success: bool
    build_tool: str  # "maven" or "gradle"
    errors: List[CompilationError]
    warnings: List[str]
    stdout_snippet: str
    stderr_snippet: str
    duration_seconds: float
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "build_tool": self.build_tool,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [
                {
                    "file": e.file,
                    "line": e.line,
                    "column": e.column,
                    "message": e.message,
                    "code": e.code,
                }
                for e in self.errors
            ],
            "warnings": self.warnings,
            "duration_seconds": self.duration_seconds,
        }


class BuildValidator:
    """Validates Spring Boot projects through compilation"""
    
    # Regex patterns for parsing Maven/Gradle output
    MAVEN_ERROR_PATTERN = re.compile(
        r'\[ERROR\]\s+(?P<file>[^\s]+):(?P<line>\d+):(?P<column>\d+):\s+(?P<code>[^:]+):\s+(?P<message>.+)'
    )
    MAVEN_COMPILE_ERROR = re.compile(
        r'(?P<file>\[.+\][^:]+):(?P<line>\d+):(?P<column>\d+):\s+(?P<message>.+)'
    )
    GRADLE_ERROR_PATTERN = re.compile(
        r'error:\s+(?P<message>.+)\s+at\s+(?P<file>[^:]+):(?P<line>\d+)'
    )
    
    def __init__(self, timeout_seconds: int = 180):
        self.timeout_seconds = timeout_seconds
        self._check_build_tools()
    
    def _check_build_tools(self):
        """Check which build tools are available"""
        self.has_maven = self._tool_exists("mvn") or self._tool_exists("mvn.cmd")
        self.has_gradle = self._tool_exists("gradle") or self._tool_exists("gradle.bat")
        
        if not self.has_maven and not self.has_gradle:
            logger.warning("No build tools found: install Maven or Gradle to enable build validation")
    
    @staticmethod
    def _tool_exists(tool_name: str) -> bool:
        """Check if a tool is available in PATH"""
        try:
            subprocess.run([tool_name, "--version"], 
                          capture_output=True, 
                          timeout=5,
                          check=False)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    async def validate_project(self, project_root: str) -> BuildResult:
        """
        Validate a Spring Boot project by attempting to compile it
        
        Args:
            project_root: Root directory of the generated project
        
        Returns:
            BuildResult with compilation status and errors
        """
        if not os.path.isdir(project_root):
            return BuildResult(
                success=False,
                build_tool="none",
                errors=[],
                warnings=[],
                stdout_snippet=f"Project directory not found: {project_root}",
                stderr_snippet="",
                duration_seconds=0.0,
            )
        
        # Try Maven first if available
        if self.has_maven:
            result = await self._validate_with_maven(project_root)
            if result:
                return result
        
        # Fall back to Gradle if available
        if self.has_gradle:
            result = await self._validate_with_gradle(project_root)
            if result:
                return result
        
        # No build tools available
        return BuildResult(
            success=False,
            build_tool="none",
            errors=[],
            warnings=["Build validation skipped: No Maven or Gradle found. Install one to enable compilation testing."],
            stdout_snippet="",
            stderr_snippet="",
            duration_seconds=0.0,
        )
    
    async def _validate_with_maven(self, project_root: str) -> Optional[BuildResult]:
        """Attempt validation with Maven"""
        pom_path = os.path.join(project_root, "pom.xml")
        if not os.path.exists(pom_path):
            return None
        
        logger.info(f"Validating project with Maven at {project_root}")
        
        try:
            proc = subprocess.Popen(
                ["mvn", "clean", "compile", "-q"],
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            stdout, stderr = proc.communicate(timeout=self.timeout_seconds)
            
            errors = self._parse_maven_errors(stderr or stdout)
            success = proc.returncode == 0 and not errors
            
            return BuildResult(
                success=success,
                build_tool="maven",
                errors=errors,
                warnings=[] if success else [line for line in (stderr or stdout).split('\n') if 'warning' in line.lower()][:10],
                stdout_snippet=(stdout or "")[-500:],
                stderr_snippet=(stderr or "")[-500:],
                duration_seconds=0.0,  # Could measure actual time
            )
        
        except subprocess.TimeoutExpired:
            logger.error("Maven build timed out")
            return BuildResult(
                success=False,
                build_tool="maven",
                errors=[],
                warnings=[f"Build timeout after {self.timeout_seconds} seconds"],
                stdout_snippet="",
                stderr_snippet="",
                duration_seconds=self.timeout_seconds,
            )
    
    async def _validate_with_gradle(self, project_root: str) -> Optional[BuildResult]:
        """Attempt validation with Gradle"""
        gradle_path = os.path.join(project_root, "build.gradle")
        gradle_kts_path = os.path.join(project_root, "build.gradle.kts")
        
        if not os.path.exists(gradle_path) and not os.path.exists(gradle_kts_path):
            return None
        
        logger.info(f"Validating project with Gradle at {project_root}")
        
        try:
            proc = subprocess.Popen(
                ["gradle", "clean", "build", "-q"],
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            stdout, stderr = proc.communicate(timeout=self.timeout_seconds)
            
            errors = self._parse_gradle_errors(stderr or stdout)
            success = proc.returncode == 0 and not errors
            
            return BuildResult(
                success=success,
                build_tool="gradle",
                errors=errors,
                warnings=[] if success else [line for line in (stderr or stdout).split('\n') if 'warning' in line.lower()][:10],
                stdout_snippet=(stdout or "")[-500:],
                stderr_snippet=(stderr or "")[-500:],
                duration_seconds=0.0,
            )
        
        except subprocess.TimeoutExpired:
            logger.error("Gradle build timed out")
            return BuildResult(
                success=False,
                build_tool="gradle",
                errors=[],
                warnings=[f"Build timeout after {self.timeout_seconds} seconds"],
                stdout_snippet="",
                stderr_snippet="",
                duration_seconds=self.timeout_seconds,
            )
    
    def _parse_maven_errors(self, output: str) -> List[CompilationError]:
        """Parse Maven error output"""
        errors: List[CompilationError] = []
        
        for match in self.MAVEN_ERROR_PATTERN.finditer(output):
            try:
                errors.append(CompilationError(
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=int(match.group("column")),
                    message=match.group("message").strip(),
                    code=match.group("code").strip(),
                ))
            except (ValueError, AttributeError):
                pass
        
        # Try alternative pattern
        for line in output.split('\n'):
            if '[ERROR]' in line and '.java' in line:
                match = self.MAVEN_COMPILE_ERROR.search(line)
                if match and len(errors) < 50:  # Limit to first 50
                    try:
                        errors.append(CompilationError(
                            file=match.group("file"),
                            line=int(match.group("line")),
                            column=int(match.group("column")),
                            message=match.group("message").strip(),
                            code="compilation_error",
                        ))
                    except (ValueError, AttributeError):
                        pass
        
        return errors[:50]  # Limit to 50 most recent errors
    
    def _parse_gradle_errors(self, output: str) -> List[CompilationError]:
        """Parse Gradle error output"""
        errors: List[CompilationError] = []
        
        for match in self.GRADLE_ERROR_PATTERN.finditer(output):
            try:
                errors.append(CompilationError(
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=0,
                    message=match.group("message").strip(),
                    code="gradle_compilation_error",
                ))
            except (ValueError, AttributeError):
                pass
        
        return errors[:50]


class DockeredBuildValidator:
    """
    Executes builds in a containerized environment for safety
    
    This prevents malicious or broken builds from affecting the host system
    """
    
    DOCKER_IMAGE = "maven:3.9-eclipse-temurin-21"
    
    def __init__(self):
        self.has_docker = self._check_docker()
    
    @staticmethod
    def _check_docker() -> bool:
        """Check if Docker is available"""
        try:
            subprocess.run(["docker", "--version"], 
                          capture_output=True, 
                          timeout=5,
                          check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False
    
    async def validate_in_container(self, project_root: str) -> BuildResult:
        """
        Validate project inside a Docker container
        
        Args:
            project_root: Path to the Spring Boot project
        
        Returns:
            BuildResult from containerized build
        """
        if not self.has_docker:
            logger.warning("Docker not available, cannot run sandboxed build")
            return BuildResult(
                success=False,
                build_tool="docker",
                errors=[],
                warnings=["Docker not available for sandboxed build"],
                stdout_snippet="",
                stderr_snippet="",
                duration_seconds=0.0,
            )
        
        # This would be implemented with docker run commands
        # For now, return a result indicating it's not yet implemented
        return BuildResult(
            success=False,
            build_tool="docker",
            errors=[],
            warnings=["Docker sandboxed builds not yet implemented"],
            stdout_snippet="",
            stderr_snippet="",
            duration_seconds=0.0,
        )


# Convenience function
async def validate_build_quality(project_root: str, 
                                 use_docker: bool = False) -> Dict:
    """
    Validate build quality of a generated Spring Boot project
    
    Args:
        project_root: Root directory of generated project
        use_docker: Whether to use containerized validation
    
    Returns:
        Dictionary with build validation results
    """
    if use_docker:
        validator = DockeredBuildValidator()
        result = await validator.validate_in_container(project_root)
    else:
        validator = BuildValidator()
        result = await validator.validate_project(project_root)
    
    return result.to_dict()
