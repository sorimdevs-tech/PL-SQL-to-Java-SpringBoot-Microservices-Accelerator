"""
Spring Boot Project Generator for PL/SQL Modernization Platform
Generates complete Spring Boot projects from converted Java code
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
import logging

# Import platform utilities
from ..utils.logger import get_logger
from ..utils.config import get_config_value

logger = get_logger(__name__)


@dataclass
class ProjectStructure:
    """Represents the generated project structure"""
    project_name: str
    package_name: str
    java_version: str
    spring_boot_version: str
    base_path: Path
    modules: List[str]
    dependencies: List[str]


class SpringBootGenerator:
    """Generates complete Spring Boot projects"""

    RESERVED_ENTITY_NAMES = {
        'Order',
        'User',
        'Group',
        'Table',
        'Column',
        'Index',
        'Key',
        'Value',
        'Constraint',
    }

    EXTRA_DEPENDENCY_COORDINATES = {
        "spring-retry": {
            "group": "org.springframework.retry",
            "artifact": "spring-retry",
            "gradle": "implementation",
        },
        "mapstruct": {
            "group": "org.mapstruct",
            "artifact": "mapstruct",
            "gradle": "implementation",
        },
        "flyway-core": {
            "group": "org.flywaydb",
            "artifact": "flyway-core",
            "gradle": "implementation",
        },
        "micrometer-registry-prometheus": {
            "group": "io.micrometer",
            "artifact": "micrometer-registry-prometheus",
            "gradle": "runtimeOnly",
        },
        "spring-boot-starter-security": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-security",
            "gradle": "implementation",
        },
        "spring-boot-starter-cache": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-cache",
            "gradle": "implementation",
        },
        "spring-boot-starter-batch": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-batch",
            "gradle": "implementation",
        },
        "spring-boot-starter-mail": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-mail",
            "gradle": "implementation",
        },
        "spring-boot-starter-webflux": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-webflux",
            "gradle": "implementation",
        },
        "spring-boot-starter-data-redis": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-data-redis",
            "gradle": "implementation",
        },
        "spring-boot-starter-data-mongodb": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-data-mongodb",
            "gradle": "implementation",
        },
        "spring-boot-starter-amqp": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-amqp",
            "gradle": "implementation",
        },
        "spring-boot-starter-quartz": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-quartz",
            "gradle": "implementation",
        },
        "spring-boot-starter-actuator": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-actuator",
            "gradle": "implementation",
        },
        "lombok": {
            "group": "org.projectlombok",
            "artifact": "lombok",
            "gradle": "compileOnly",
            "annotationProcessor": True,
            "scope": "provided",
            "optional": True,
        },
    }

    BASE_DEPENDENCY_IDS = {
        "spring-boot-starter-web",
        "spring-boot-starter-data-jpa",
        "spring-boot-starter-validation",
        "springdoc-openapi-starter-webmvc-ui",
        "ojdbc8",
        "mysql-connector-j",
        "postgresql",
        "spring-boot-starter-test",
        "testcontainers",
        "junit-jupiter",
        "spring-boot-devtools",
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Spring Boot generator
        
        Args:
            config (Dict[str, Any]): Output configuration
        """
        self.config = config
        self.project_name = config.get('project_name', 'converted-app')
        self.group_id = config.get('group_id', 'com.company')
        self.artifact_id = config.get('artifact_id', self.project_name)
        self.package_name = config.get('package_name', 'com.company.project')
        self.description = config.get('description', 'PL/SQL to Java Modernization Project')
        self.java_version = config.get('java_version', '17')
        self.spring_boot_version = config.get('spring_boot_version', '3.1.0')
        self.build_tool = self._normalize_build_tool(config.get('build_tool', 'maven'))
        self.packaging = self._normalize_packaging(config.get('packaging', 'jar'))
        self.config_format = self._normalize_config_format(config.get('config_format', 'properties'))
        self.target_directory = Path(config.get('target_directory', './output'))
        self.extra_dependencies = self._normalize_extra_dependencies(config.get('dependencies', []))
        self._existing_repositories: Set[str] = set()
        
        # Create standard Spring Boot source layout.
        self.base_path = self.target_directory / 'src' / 'main' / 'java'
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.resources_path = self.target_directory / 'src' / 'main' / 'resources'
        self.test_base_path = self.target_directory / 'src' / 'test' / 'java'
        
        # Package structure paths
        self.package_path = self.base_path / self.package_name.replace('.', '/')
        
        logger.info(f"Spring Boot Generator initialized for project: {self.project_name}")

    def _normalize_extra_dependencies(self, dependencies: List[str]) -> List[str]:
        normalized: List[str] = []
        for dep in dependencies or []:
            if not dep:
                continue
            dep_id = str(dep).strip()
            if not dep_id or dep_id in self.BASE_DEPENDENCY_IDS:
                continue
            if ":" in dep_id:
                if dep_id not in normalized:
                    normalized.append(dep_id)
                continue
            if dep_id in self.EXTRA_DEPENDENCY_COORDINATES and dep_id not in normalized:
                normalized.append(dep_id)
        return normalized

    def _render_extra_maven_dependencies(self) -> str:
        if not self.extra_dependencies:
            return ""
        blocks: List[str] = []
        for dep_id in self.extra_dependencies:
            info = self.EXTRA_DEPENDENCY_COORDINATES.get(dep_id)
            if not info:
                coordinate_parts = dep_id.split(":")
                if len(coordinate_parts) >= 2:
                    group_id = coordinate_parts[0]
                    artifact_id = coordinate_parts[1]
                    lines = [
                        "<dependency>",
                        f"    <groupId>{group_id}</groupId>",
                        f"    <artifactId>{artifact_id}</artifactId>",
                        "</dependency>",
                    ]
                    blocks.append("\n        ".join(lines))
                continue
            scope = info.get("scope")
            optional = info.get("optional")
            lines = [
                "<dependency>",
                f"    <groupId>{info['group']}</groupId>",
                f"    <artifactId>{info['artifact']}</artifactId>",
            ]
            if scope:
                lines.append(f"    <scope>{scope}</scope>")
            if optional:
                lines.append("    <optional>true</optional>")
            lines.append("</dependency>")
            blocks.append("\n        ".join(lines))
        if not blocks:
            return ""
        return "\n        " + "\n        ".join(blocks)

    def _render_extra_gradle_dependencies(self) -> str:
        if not self.extra_dependencies:
            return ""
        lines: List[str] = []
        for dep_id in self.extra_dependencies:
            info = self.EXTRA_DEPENDENCY_COORDINATES.get(dep_id)
            if not info:
                coordinate_parts = dep_id.split(":")
                if len(coordinate_parts) >= 2:
                    coordinate = f"{coordinate_parts[0]}:{coordinate_parts[1]}"
                    lines.append(f"implementation '{coordinate}'")
                continue
            coordinate = f"{info['group']}:{info['artifact']}"
            if dep_id == "lombok":
                lines.append(f"compileOnly '{coordinate}'")
                if info.get("annotationProcessor"):
                    lines.append(f"annotationProcessor '{coordinate}'")
                continue
            config = info.get("gradle", "implementation")
            lines.append(f"{config} '{coordinate}'")
        if not lines:
            return ""
        return "\n    " + "\n    ".join(lines)
    
    async def generate_project(self, java_code: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate complete Spring Boot project
        
        Args:
            java_code (Dict[str, str]): Generated Java code files
            
        Returns:
            Dict[str, Any]: Project generation results
        """
        logger.info("Starting Spring Boot project generation...")
        # Keep a copy for downstream normalization/generation steps.
        self._latest_java_code = dict(java_code or {})
        
        # Create project structure
        self._create_project_structure()
        
        # Generate Maven/Gradle configuration
        self._generate_build_config()
        
        # Generate application configuration
        self._generate_application_config()
        
        # Generate Java files
        java_files = self._generate_java_files(java_code)

        # Safety cleanup: remove any accidentally generated repository stubs that shadow Spring classes.
        repo_dir = self.package_path / 'repository'
        for reserved in ('JpaRepository.java', 'CrudRepository.java'):
            reserved_path = repo_dir / reserved
            if reserved_path.exists():
                reserved_path.unlink()

        # Generate additional configuration files
        self._generate_additional_configs()
        
        # Generate README
        self._generate_readme()
        
        # Generate project summary
        project_summary = self._generate_project_summary(java_files)
        
        logger.info(f"Spring Boot project generation completed. Generated {len(java_files)} files.")
        
        return {
            'project_name': self.project_name,
            'package_name': self.package_name,
            'base_path': str(self.base_path),
            'java_files': java_files,
            'project_structure': project_summary
        }
    
    def _create_project_structure(self):
        """Create the basic Spring Boot project structure"""
        # Main source directories
        (self.package_path / 'controller').mkdir(parents=True, exist_ok=True)
        (self.package_path / 'service').mkdir(parents=True, exist_ok=True)
        (self.package_path / 'repository').mkdir(parents=True, exist_ok=True)
        (self.package_path / 'entity').mkdir(parents=True, exist_ok=True)
        (self.package_path / 'dto').mkdir(parents=True, exist_ok=True)
        (self.package_path / 'exception').mkdir(parents=True, exist_ok=True)
        (self.package_path / 'config').mkdir(parents=True, exist_ok=True)
        
        # Test directories
        test_path = self.test_base_path / self.package_name.replace('.', '/')
        (test_path / 'service').mkdir(parents=True, exist_ok=True)
        (test_path / 'repository').mkdir(parents=True, exist_ok=True)
        (test_path / 'controller').mkdir(parents=True, exist_ok=True)
        (test_path / 'entity').mkdir(parents=True, exist_ok=True)
        (test_path / 'integration').mkdir(parents=True, exist_ok=True)
        
        # Resources directory
        self.resources_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("Project structure created successfully")
    
    def _generate_build_config(self):
        """Generate Maven POM or Gradle build file"""
        if self.build_tool == "gradle":
            gradle_content = self._generate_gradle_content()
            gradle_path = self.target_directory / 'build.gradle'
            with open(gradle_path, 'w', encoding='utf-8') as f:
                f.write(gradle_content)
        else:
            pom_content = self._generate_pom_content()
            pom_path = self.target_directory / 'pom.xml'
            with open(pom_path, 'w', encoding='utf-8') as f:
                f.write(pom_content)
        
        logger.info("Build configuration files generated")
    
    def _generate_pom_content(self) -> str:
        """Generate Maven POM content"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>{self.spring_boot_version}</version>
        <relativePath/>
    </parent>

    <groupId>{self.group_id}</groupId>
    <artifactId>{self.artifact_id}</artifactId>
    <version>1.0.0</version>
    <name>{self.project_name}</name>
    <description>{self.description}</description>
    <packaging>{self.packaging}</packaging>

    <properties>
        <java.version>{self.java_version}</java.version>
        <maven.compiler.source>{self.java_version}</maven.compiler.source>
        <maven.compiler.target>{self.java_version}</maven.compiler.target>
    </properties>

    <dependencies>
        <!-- Spring Boot Starters -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
            <version>2.5.0</version>
        </dependency>
        
        <!-- Database Drivers -->
        <dependency>
            <groupId>com.oracle.database.jdbc</groupId>
            <artifactId>ojdbc8</artifactId>
            <scope>runtime</scope>
        </dependency>
        
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>
        
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        
        <!-- Testing -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>testcontainers</artifactId>
            <scope>test</scope>
        </dependency>
        
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        
        <!-- Development Tools -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-devtools</artifactId>
            <scope>runtime</scope>
            <optional>true</optional>
        </dependency>
        {self._render_extra_maven_dependencies()}
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
            
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
                <configuration>
                    <source>{self.java_version}</source>
                    <target>{self.java_version}</target>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""
    
    def _generate_gradle_content(self) -> str:
        """Generate Gradle build file content"""
        war_plugin = "    id 'war'\n" if self.packaging == "war" else ""
        war_tasks = ""
        if self.packaging == "war":
            war_tasks = """

bootJar {
    enabled = false
}

bootWar {
    enabled = true
}
"""
        return f"""plugins {{
    id 'org.springframework.boot' version '{self.spring_boot_version}'
    id 'io.spring.dependency-management' version '1.1.3'
    id 'java'
{war_plugin}}}

group = '{self.group_id}'
version = '1.0.0'
description = '{self.description}'

java {{
    sourceCompatibility = JavaVersion.VERSION_{self.java_version}
    targetCompatibility = JavaVersion.VERSION_{self.java_version}
}}

repositories {{
    mavenCentral()
}}

dependencies {{
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    implementation 'org.springdoc:springdoc-openapi-starter-webmvc-ui:2.5.0'
    
    runtimeOnly 'com.oracle.database.jdbc:ojdbc8'
    runtimeOnly 'mysql:mysql-connector-java'
    runtimeOnly 'org.postgresql:postgresql'
    
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.testcontainers:testcontainers'
    testImplementation 'org.testcontainers:junit-jupiter'
    
    developmentOnly 'org.springframework.boot:spring-boot-devtools'
{self._render_extra_gradle_dependencies()}
}}

tasks.named('test') {{
    useJUnitPlatform()
}}
{war_tasks}
"""
    
    def _generate_application_config(self):
        """Generate Spring Boot application configuration"""
        if self.config_format == "yaml":
            app_config = self._generate_application_yml()
            config_path = self.resources_path / 'application.yml'
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(app_config)
        else:
            app_props = self._generate_application_properties()
            props_path = self.resources_path / 'application.properties'
            with open(props_path, 'w', encoding='utf-8') as f:
                f.write(app_props)
        
        logger.info("Application configuration files generated")
    
    def _generate_application_yml(self) -> str:
        """Generate application.yml content"""
        return f"""# Spring Boot Application Configuration
spring:
  application:
    name: {self.project_name}
  
  # Database Configuration
  datasource:
    url: jdbc:oracle:thin:@localhost:1521:xe
    username: your_username
    password: your_password
    driver-class-name: oracle.jdbc.OracleDriver
  
  # JPA Configuration
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: true
    properties:
      hibernate:
        dialect: org.hibernate.dialect.OracleDialect
        format_sql: true
  
  # Server Configuration
  server:
    port: 8080
  
  # Logging Configuration
  logging:
    level:
      {self.package_name}: DEBUG
      org.hibernate.SQL: DEBUG
      org.springframework.data.jpa.repository: DEBUG

# Custom Application Properties
app:
  version: 1.0.0
  description: {self.description}
  build-time: {self._get_current_time()}
"""
    
    def _generate_application_properties(self) -> str:
        """Generate application.properties content"""
        return f"""# Spring Boot Application Configuration
spring.application.name={self.project_name}

# Database Configuration
spring.datasource.url=jdbc:oracle:thin:@localhost:1521:xe
spring.datasource.username=your_username
spring.datasource.password=your_password
spring.datasource.driver-class-name=oracle.jdbc.OracleDriver

# JPA Configuration
spring.jpa.hibernate.ddl-auto=update
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.OracleDialect
spring.jpa.properties.hibernate.format_sql=true

# Server Configuration
spring.server.port=8080

# Logging Configuration
logging.level.{self.package_name}=DEBUG
logging.level.org.hibernate.SQL=DEBUG
logging.level.org.springframework.data.jpa.repository=DEBUG

# Custom Application Properties
app.version=1.0.0
app.description={self.description}
app.build-time={self._get_current_time()}
"""

    def _normalize_build_tool(self, value: str) -> str:
        if not value:
            return "maven"
        lowered = str(value).strip().lower()
        if lowered in {"mvn", "maven"}:
            return "maven"
        if lowered in {"gradle", "gradle-groovy", "gradle-kotlin"}:
            return "gradle"
        return "maven"

    def _normalize_packaging(self, value: str) -> str:
        lowered = str(value or "").strip().lower()
        return "war" if lowered == "war" else "jar"

    def _normalize_config_format(self, value: str) -> str:
        lowered = str(value or "").strip().lower()
        return "yaml" if lowered in {"yaml", "yml"} else "properties"
    
    def _generate_java_files(self, java_code: Dict[str, str]) -> Dict[str, str]:
        """Generate Java source files"""
        java_files = {}
        
        for filename, code in java_code.items():
            type_name = self._extract_type_name(code)
            if (type_name in {'JpaRepository', 'CrudRepository'}
                or filename.lower() in {'jparepository.java', 'crudrepository.java'}):
                continue
            target_filename = f"{type_name}.java" if type_name else filename
            # Determine the appropriate package directory
            file_type = self._classify_java_file(target_filename, code)
            if file_type == 'repository' and type_name in {'JpaRepository', 'CrudRepository'}:
                continue
            if file_type == 'repository' and target_filename.lower() in {'jparepository.java', 'crudrepository.java'}:
                continue
            target_dir = self._get_target_directory(file_type)
            
            # Create directory if it doesn't exist
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Write the Java file
            file_path = target_dir / target_filename
            payload = code
            if file_type == 'repository':
                payload = self._normalize_repository_code(target_filename, code, getattr(self, "_ddl_table_map", None))
                repo_interface = self._extract_type_name(payload)
                if repo_interface:
                    self._existing_repositories.add(repo_interface)
            elif file_type == 'entity':
                payload = self._normalize_entity_code(target_filename, code)
            elif file_type == 'controller':
                payload = self._normalize_controller_code(target_filename, code)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(payload)
            
            java_files[target_filename] = str(file_path)
        
        # Generate additional Java files
        self._generate_additional_java_files()
        
        logger.info(f"Generated {len(java_files)} Java source files")
        return java_files
    
    def _classify_java_file(self, filename: str, code: str) -> str:
        """Classify Java file by type"""
        filename_lower = filename.lower()

        if any(token in code for token in ('@Entity', '@Table', '@Id', '@Column')):
            return 'entity'
        if 'JpaRepository' in code or 'CrudRepository' in code or '@Repository' in code:
            return 'repository'

        if 'controller' in filename_lower or 'rest' in filename_lower:
            return 'controller'
        elif 'service' in filename_lower:
            return 'service'
        elif 'repository' in filename_lower or 'dao' in filename_lower:
            return 'repository'
        elif 'entity' in filename_lower or 'model' in filename_lower:
            return 'entity'
        elif 'dto' in filename_lower or 'request' in filename_lower or 'response' in filename_lower:
            return 'dto'
        elif 'exception' in filename_lower:
            return 'exception'
        elif 'config' in filename_lower:
            return 'config'
        else:
            # Analyze code content to determine type
            if '@RestController' in code or '@Controller' in code:
                return 'controller'
            elif '@Service' in code:
                return 'service'
            elif '@Repository' in code:
                return 'repository'
            elif '@Entity' in code:
                return 'entity'
            elif '@Configuration' in code:
                return 'config'
            else:
                return 'service'  # Default to service
    
    def _get_target_directory(self, file_type: str) -> Path:
        """Get target directory for file type"""
        if file_type == 'controller':
            return self.package_path / 'controller'
        elif file_type == 'service':
            return self.package_path / 'service'
        elif file_type == 'repository':
            return self.package_path / 'repository'
        elif file_type == 'entity':
            return self.package_path / 'entity'
        elif file_type == 'dto':
            return self.package_path / 'dto'
        elif file_type == 'exception':
            return self.package_path / 'exception'
        elif file_type == 'config':
            return self.package_path / 'config'
        else:
            return self.package_path / 'service'
    
    def _generate_additional_java_files(self):
        """Generate additional Java files needed for Spring Boot application"""
        # Generate main application class
        main_class = self._generate_main_application_class()
        main_path = self.package_path / f"{self._to_camel_case(self.project_name)}Application.java"
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(main_class)
        
        # Generate exception classes
        base_exceptions = self._generate_base_exceptions()
        for class_name, content in base_exceptions.items():
            exception_path = self.package_path / 'exception' / f"{class_name}.java"
            with open(exception_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Generate DTO base classes
        base_dto = self._generate_base_dto()
        dto_path = self.package_path / 'dto' / 'BaseDTO.java'
        with open(dto_path, 'w', encoding='utf-8') as f:
            f.write(base_dto)
        
        # Generate configuration classes
        config_classes = self._generate_config_classes()
        for class_name, content in config_classes.items():
            config_path = self.package_path / 'config' / f"{class_name}.java"
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def _generate_main_application_class(self) -> str:
        """Generate main Spring Boot application class"""
        return f"""package {self.package_name};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * Main application class for {self.project_name}
 * 
 * This class serves as the entry point for the Spring Boot application
 * generated from PL/SQL modernization.
 */
@SpringBootApplication
@EnableJpaRepositories(basePackages = "{self.package_name}.repository")
@EnableTransactionManagement
public class {self._to_camel_case(self.project_name)}Application {{
    
    public static void main(String[] args) {{
        SpringApplication.run({self._to_camel_case(self.project_name)}Application.class, args);
    }}
}}
"""
    
    def _generate_base_exceptions(self) -> Dict[str, str]:
        """Generate exception classes"""
        return {
            "BusinessException": f"""package {self.package_name}.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.BAD_REQUEST)
public class BusinessException extends RuntimeException {{
    public BusinessException(String message) {{
        super(message);
    }}

    public BusinessException(String message, Throwable cause) {{
        super(message, cause);
    }}
}}
""",
            "ResourceNotFoundException": f"""package {self.package_name}.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.NOT_FOUND)
public class ResourceNotFoundException extends RuntimeException {{
    public ResourceNotFoundException(String message) {{
        super(message);
    }}

    public ResourceNotFoundException(String message, Throwable cause) {{
        super(message, cause);
    }}
}}
""",
            "ValidationException": f"""package {self.package_name}.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.BAD_REQUEST)
public class ValidationException extends RuntimeException {{
    public ValidationException(String message) {{
        super(message);
    }}

    public ValidationException(String message, Throwable cause) {{
        super(message, cause);
    }}
}}
"""
        }
    
    def _generate_base_dto(self) -> str:
        """Generate base DTO class"""
        return f"""package {self.package_name}.dto;

import java.io.Serializable;

/**
 * Base DTO class providing common functionality
 */
public abstract class BaseDTO implements Serializable {{
    
    private static final long serialVersionUID = 1L;
    
    /**
     * Convert DTO to entity
     * @return Entity representation
     */
    public abstract Object toEntity();
    
    /**
     * Convert entity to DTO
     * @param entity Entity to convert
     * @return DTO representation
     */
    public static <T extends BaseDTO> T fromEntity(Object entity) {{
        // Implementation would depend on specific DTO type
        throw new UnsupportedOperationException("Implement in concrete DTO classes");
    }}
}}
"""
    
    def _generate_config_classes(self) -> Dict[str, str]:
        """Generate configuration classes"""
        return {
            'DatabaseConfig': f"""package {self.package_name}.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * Database configuration class
 */
@Configuration
@EnableJpaAuditing
@EnableTransactionManagement
public class DatabaseConfig {{
    // Database-specific configurations can be added here
}}
""",
            
            'WebConfig': f"""package {self.package_name}.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web configuration class
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {{
    
    @Override
    public void addCorsMappings(CorsRegistry registry) {{
        registry.addMapping("/**")
                .allowedOrigins("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(false);
    }}
}}
""",
            
            'SwaggerConfig': f"""package {self.package_name}.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Swagger/OpenAPI configuration
 */
@Configuration
public class SwaggerConfig {{
    
    @Bean
    public OpenAPI customOpenAPI() {{
        return new OpenAPI()
                .info(new Info()
                        .title("{self.project_name}")
                        .version("1.0.0")
                        .description("API documentation for the PL/SQL modernization project"));
    }}
}}
"""
        }
    
    def _generate_additional_configs(self):
        """Generate additional configuration files"""
        # Generate Dockerfile
        dockerfile = self._generate_dockerfile()
        docker_path = self.target_directory / 'Dockerfile'
        with open(docker_path, 'w', encoding='utf-8') as f:
            f.write(dockerfile)
        
        # Generate .gitignore
        gitignore = self._generate_gitignore()
        gitignore_path = self.target_directory / '.gitignore'
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(gitignore)
        
        # Generate README for the project
        project_readme = self._generate_project_readme()
        readme_path = self.target_directory / 'README.md'
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(project_readme)
        
        logger.info("Additional configuration files generated")
    
    def _generate_dockerfile(self) -> str:
        """Generate Dockerfile for the application"""
        return f"""# Use official OpenJDK runtime as base image
FROM openjdk:17-jdk-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the JAR file into the container
COPY target/{self.project_name}-1.0.0.jar app.jar

# Expose the port the app runs on
EXPOSE 8080

# Run the JAR file
ENTRYPOINT ["java", "-jar", "app.jar"]
"""
    
    def _generate_gitignore(self) -> str:
        """Generate .gitignore file"""
        return """# Compiled class file
*.class

# Log file
*.log

# BlueJ files
*.ctxt

# Mobile Tools for Java (J2ME)
.mtj.tmp/

# Package Files #
*.jar
*.war
*.nar
*.ear
*.zip
*.tar.gz
*.rar

# virtual machine crash logs
hs_err_pid*

# Maven
target/
pom.xml.tag
pom.xml.releaseBackup
pom.xml.versionsBackup
pom.xml.next
release.properties
dependency-reduced-pom.xml
buildNumber.properties
.mvn/timing.properties
.mvn/wrapper/maven-wrapper.jar

# Gradle
.gradle
build/
!gradle/wrapper/gradle-wrapper.jar
!**/src/main/**
!**/src/test/**

# IDE
.idea/
*.iws
*.iml
*.ipr
.vscode/
.settings/
.project
.classpath

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.swp
*.swo

# Application specific
application-local.yml
application-dev.yml
application-prod.yml
"""
    
    def _generate_project_readme(self) -> str:
        """Generate project README"""
        return f"""# {self.project_name}

Auto-generated Spring Boot application from PL/SQL modernization.

## Project Information

- **Package**: {self.package_name}
- **Java Version**: {self.java_version}
- **Spring Boot Version**: {self.spring_boot_version}
- **Generated**: {self._get_current_time()}

## Project Structure

```
src/
├── main/java/{self.package_name}/
│   ├── Application.java              # Main application class
│   ├── controller/                   # REST controllers
│   ├── service/                      # Business logic services
│   ├── repository/                   # JPA repositories
│   ├── entity/                       # JPA entities
│   ├── dto/                          # Data transfer objects
│   ├── exception/                    # Custom exceptions
│   └── config/                       # Configuration classes
└── main/resources/
    ├── application.yml              # Application configuration
    └── application.properties       # Alternative configuration

## Getting Started

### Prerequisites

- Java {self.java_version} or later
- Maven or Gradle
- Database (Oracle, MySQL, or PostgreSQL)

### Installation

1. Clone the repository
2. Configure database connection in `application.yml`
3. Build the project:
   ```bash
   mvn clean install
   ```
4. Run the application:
   ```bash
   mvn spring-boot:run
   ```

### Configuration

Update the database connection settings in `src/main/resources/application.yml`:

```yaml
spring:
  datasource:
    url: jdbc:oracle:thin:@localhost:1521:xe
    username: your_username
    password: your_password
```

## API Documentation

The application includes Swagger/OpenAPI documentation available at:
- http://localhost:8080/swagger-ui/index.html
- http://localhost:8080/v3/api-docs

## Generated Components

This application was automatically generated from PL/SQL code with the following components:

- **Controllers**: REST API endpoints
- **Services**: Business logic implementation
- **Repositories**: Database access layer
- **Entities**: JPA entity mappings
- **DTOs**: Data transfer objects
- **Exceptions**: Custom exception handling

## License

This project is auto-generated and does not include a specific license.
"""
    
    def _generate_readme(self):
        """Generate main README for the generated project"""
        readme_content = f"""# {self.project_name} - Generated Project

This Spring Boot project was automatically generated from PL/SQL code using the PL/SQL Modernization Platform.

## Project Details

- **Original Source**: PL/SQL Code
- **Target Framework**: Spring Boot {self.spring_boot_version}
- **Java Version**: {self.java_version}
- **Package**: {self.package_name}
- **Generation Date**: {self._get_current_time()}

## Project Structure

The generated project follows standard Spring Boot conventions:

```
{self.project_name}/
├── src/main/java/{self.package_name}/
│   ├── Application.java
│   ├── controller/
│   ├── service/
│   ├── repository/
│   ├── entity/
│   ├── dto/
│   ├── exception/
│   └── config/
├── src/main/resources/
│   ├── application.yml
│   └── application.properties
├── src/test/
├── pom.xml
├── build.gradle
├── Dockerfile
└── README.md
```

## Next Steps

1. **Configure Database**: Update connection settings in `application.yml`
2. **Review Generated Code**: Check the generated Java files for accuracy
3. **Add Tests**: Implement unit and integration tests
4. **Build and Deploy**: Use Maven or Gradle to build and deploy

## Support

For issues with the generated code, please refer to the original PL/SQL modernization documentation.
"""
        
        readme_path = self.target_directory / 'README.md'
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
    
    def _generate_project_summary(self, java_files: Dict[str, str]) -> Dict[str, Any]:
        """Generate project summary"""
        summary = {
            'project_name': self.project_name,
            'package_name': self.package_name,
            'java_version': self.java_version,
            'spring_boot_version': self.spring_boot_version,
            'total_files': len(java_files),
            'file_types': {},
            'directories': [],
            'configuration_files': [
                'pom.xml',
                'application.yml',
                'application.properties',
                'Dockerfile',
                '.gitignore'
            ]
        }
        if self.config.get('generate_gradle', False):
            summary['configuration_files'].insert(1, 'build.gradle')
        
        # Count file types
        for filename in java_files.keys():
            file_type = self._classify_java_file(filename, "")
            summary['file_types'][file_type] = summary['file_types'].get(file_type, 0) + 1
        
        # List directories
        for item in self.base_path.iterdir():
            if item.is_dir():
                summary['directories'].append(str(item.name))
        
        return summary
    
    def _to_camel_case(self, text: str) -> str:
        """Convert text to camel case"""
        return ''.join(word.capitalize() for word in text.replace('-', '_').split('_'))

    def _normalize_entity_type_name(self, raw_name: str) -> str:
        """Normalize entity type names coming from repositories or LLM output."""
        if not raw_name:
            return raw_name
        stripped = raw_name.strip()
        if stripped in {"JpaRepository", "CrudRepository"}:
            return stripped
        lower = stripped.lower()
        base = stripped
        if lower.endswith("entity"):
            base = stripped[: -6]
        if "_" in base or base[:1].islower():
            base = self._to_camel_case(base)
        if lower.endswith("entity"):
            return f"{base}Entity"
        return base
    
    def _get_current_time(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def generate_entities(
        self,
        java_code: Dict[str, str],
        ddl_columns: Optional[Dict[str, List[Dict[str, str]]]] = None,
    ) -> Dict[str, str]:
        """Generate JPA entity classes"""
        entities = {}
        ddl_columns = ddl_columns or {}
        if ddl_columns:
            logger.info(f"DDL table columns loaded for {len(ddl_columns)} tables")
        ddl_map = {table.replace("_", "").lower(): table for table in ddl_columns.keys()}
        self._ddl_table_map = ddl_map
        
        for filename, code in java_code.items():
            if '@Entity' in code or 'extends BaseEntity' in code:
                class_name = self._extract_class_name(code) or filename.replace('.java', '')
                if class_name in {"Jpa", "JpaRepository", "CrudRepository"}:
                    continue
                normalized_name = self._normalize_entity_name(class_name)
                target_filename = f"{normalized_name}.java"
                entities[target_filename] = self._rename_entity_type_references(code, class_name, normalized_name)

        # Always create entities from DDL when available, even if LLM output omitted them.
        for table_name, columns in ddl_columns.items():
            if table_name.upper() in {"JPA", "JPA_REPOSITORY", "CRUD_REPOSITORY"}:
                continue
            ddl_entity_name = f"{self._to_camel_case(table_name.lower())}Entity"
            normalized_entity_name = self._normalize_entity_name(ddl_entity_name)
            target_filename = f"{normalized_entity_name}.java"
            if target_filename in entities:
                continue
            logger.info(f"Generating entity {normalized_entity_name} from DDL table {table_name}")
            entities[target_filename] = self._generate_entity_from_ddl(
                normalized_entity_name, table_name, columns
            )

        # Ensure entities exist for service-derived repository/entity names not present in DDL.
        for filename, code in java_code.items():
            if not self._looks_like_service_source(filename, code):
                continue
            class_name = self._extract_class_name(code)
            for entity_name in self._derive_entity_names(filename, class_name, code):
                normalized_entity, table_name = self._resolve_entity_from_ddl(entity_name, ddl_map)
                normalized_entity = self._normalize_entity_name(normalized_entity)
                if normalized_entity in {"Jpa", "JpaEntity", "JpaRepository", "CrudRepository"}:
                    continue
                target_filename = f"{normalized_entity}.java"
                if target_filename in entities:
                    continue
                if table_name and table_name in ddl_columns:
                    logger.info(f"Generating entity {normalized_entity} from DDL table {table_name}")
                    entities[target_filename] = self._generate_entity_from_ddl(
                        normalized_entity, table_name, ddl_columns[table_name]
                    )
                else:
                    logger.warning(f"Generating fallback entity {normalized_entity} for service reference")
                    entities[target_filename] = self._generate_fallback_entity(normalized_entity, [])
        
        # Fallback: derive simple entities from service-oriented outputs.
        if not entities:
            for filename, code in java_code.items():
                if not self._looks_like_service_source(filename, code):
                    continue
                class_name = self._extract_class_name(code)
                for entity_name in self._derive_entity_names(filename, class_name, code):
                    normalized_entity_name = self._normalize_entity_name(entity_name)
                    fallback_name = f"{normalized_entity_name}.java"
                    if fallback_name in entities:
                        continue
                    fields = self._infer_entity_fields(code, entity_name)
                    entities[fallback_name] = self._generate_fallback_entity(entity_name, fields)

        repository_entities: Set[str] = set()
        for code in java_code.values():
            for match in re.finditer(r'extends\s+(?:JpaRepository|CrudRepository)\s*<\s*([A-Za-z_][\w$#]*)', code):
                repository_entities.add(match.group(1))
        repo_dir = self.package_path / 'repository'
        if repo_dir.exists():
            for repo_file in repo_dir.glob('*.java'):
                try:
                    repo_code = repo_file.read_text(encoding='utf-8')
                except OSError:
                    continue
                for match in re.finditer(
                    r'extends\s+(?:JpaRepository|CrudRepository)\s*<\s*([A-Za-z_][\w$#]*)',
                    repo_code,
                ):
                    repository_entities.add(match.group(1))
        for raw_entity in repository_entities:
            normalized, table_name = self._resolve_entity_from_ddl(raw_entity, ddl_map)
            normalized = self._normalize_entity_name(normalized)
            fallback_name = f"{normalized}.java"
            if fallback_name in entities:
                continue
            if table_name and table_name in ddl_columns:
                logger.info(f"Generating entity {normalized} from DDL table {table_name}")
                entities[fallback_name] = self._generate_entity_from_ddl(normalized, table_name, ddl_columns[table_name])
            else:
                missing_table = table_name or self._to_snake_case(normalized.replace("Entity", "")).upper()
                logger.warning(f"Missing DDL for entity {normalized} (table {missing_table}); using id-only fallback")
                entities[fallback_name] = self._generate_fallback_entity(normalized, [])

        for filename, code in list(entities.items()):
            if not self._entity_has_meaningful_fields(code):
                entity_name = filename.replace('.java', '')
                normalized, table_name = self._resolve_entity_from_ddl(entity_name, ddl_map)
                if table_name and table_name in ddl_columns:
                    logger.info(f"Upgrading entity {entity_name} with DDL table {table_name}")
                    entities[filename] = self._generate_entity_from_ddl(normalized, table_name, ddl_columns[table_name])
        
        # Write entities to files
        entity_dir = self.package_path / 'entity'
        for filename, code in entities.items():
            file_path = entity_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

        if ddl_map:
            self._rewrite_repository_entities(ddl_map)

        logger.info(f"Generated {len(entities)} entity classes")
        return entities

    def _extract_class_name(self, code: str) -> Optional[str]:
        """Extract top-level class name from Java source."""
        for line in code.splitlines():
            stripped = line.strip()
            if stripped.startswith('public class '):
                return stripped.split()[2].split('{')[0].strip()
        return None

    def _extract_type_name(self, code: str) -> Optional[str]:
        """Extract top-level public class or interface name from Java source."""
        for line in code.splitlines():
            stripped = line.strip()
            if stripped.startswith('public class '):
                return stripped.split()[2].split('{')[0].strip()
            if stripped.startswith('public interface '):
                return stripped.split()[2].split('{')[0].strip()
        return None

    def _resolve_entity_from_ddl(self, raw_entity: str, ddl_map: Dict[str, str]) -> Tuple[str, Optional[str]]:
        """Resolve an entity name using DDL table names when possible."""
        if not raw_entity:
            return raw_entity, None
        raw = raw_entity.strip()
        lowered = raw.lower()
        base = raw
        if lowered.endswith("entity"):
            base = raw[: -6]
        base_key = base.replace("_", "").lower()
        if base_key in ddl_map:
            table_name = ddl_map[base_key]
            entity_name = f"{self._to_camel_case(table_name.lower())}Entity"
            return entity_name, table_name
        return self._normalize_entity_type_name(raw), None

    def _rewrite_repository_entities(self, ddl_map: Dict[str, str]) -> None:
        repo_dir = self.package_path / 'repository'
        if not repo_dir.exists():
            return
        for repo_file in repo_dir.glob('*.java'):
            try:
                repo_code = repo_file.read_text(encoding='utf-8')
            except OSError:
                continue
            updated = self._normalize_repository_code(repo_file.name, repo_code, ddl_map)
            if updated != repo_code:
                repo_file.write_text(updated, encoding='utf-8')
    
    def _derive_entity_name(self, filename: str, class_name: Optional[str]) -> Optional[str]:
        """Derive a single fallback entity name from class or file name."""
        if class_name and class_name.lower().endswith('service'):
            base = class_name[:-7]
            return base if base else None
        if filename.lower().endswith('service.java'):
            base = filename[:-12]
            return self._to_camel_case(base) if base else None
        stem = filename.replace('.java', '')
        if stem:
            return self._to_camel_case(stem)
        return None

    def _derive_entity_names(self, filename: str, class_name: Optional[str], code: str) -> List[str]:
        """Derive all entity names referenced by a generated service."""
        entity_names: List[str] = []

        for match in re.finditer(r'new\s+([A-Z]\w*)\s*\(', code):
            candidate = match.group(1)
            if self._is_entity_candidate_name(candidate):
                entity_names.append(candidate)

        for match in re.finditer(r'\b([A-Z]\w*)Repository\b', code):
            candidate = match.group(1)
            if self._is_entity_candidate_name(candidate):
                entity_names.append(candidate)

        fallback_name = self._derive_entity_name(filename, class_name)
        if fallback_name and not entity_names:
            entity_names.append(fallback_name)

        ordered: List[str] = []
        seen = set()
        for name in entity_names:
            if name and name not in seen:
                ordered.append(name)
                seen.add(name)
        return ordered

    def _normalize_entity_name(self, entity_name: str) -> str:
        """Append Entity to reserved names that would otherwise clash or read ambiguously."""
        if entity_name in self.RESERVED_ENTITY_NAMES:
            return f"{entity_name}Entity"
        return entity_name

    def _rename_entity_type_references(self, code: str, source_name: str, target_name: str) -> str:
        """Rename a Java entity type and aligned repository references."""
        if not source_name or source_name == target_name:
            return code

        updated_code = re.sub(rf'\b{re.escape(source_name)}Repository\b', f'{target_name}Repository', code)
        updated_code = re.sub(rf'\b{re.escape(source_name)}\b', target_name, updated_code)
        return updated_code

    def _is_entity_candidate_name(self, candidate: str) -> bool:
        """Exclude helper/result/exception names from fallback entity generation."""
        blocked_suffixes = ('Exception', 'Result', 'Response', 'Request', 'DTO', 'Config', 'Controller', 'Service')
        blocked_names = {'BusinessException', 'IllegalArgumentException', 'ProcessOrderResult', 'TABLE'}
        return bool(candidate) and candidate not in blocked_names and not candidate.endswith(blocked_suffixes)

    def _looks_like_service_source(self, filename: str, code: str) -> bool:
        """Limit fallback entity generation to service-like Java sources."""
        class_name = self._extract_class_name(code) or ''
        filename_lower = filename.lower()
        return (
            '@Service' in code
            or filename_lower.endswith('service.java')
            or class_name.lower().endswith('service')
            or 'processOrder(' in code
        )
    
    def _infer_entity_fields(self, code: str, entity_name: str) -> List[Dict[str, str]]:
        """Infer entity fields from generated service code usage for a specific entity."""
        param_types: Dict[str, str] = {}
        local_types: Dict[str, str] = {}
        entity_variables: set[str] = set()

        # Capture method parameter types so setter arguments can map back to Java types.
        for match in re.finditer(r'public\s+[^{;=]+\(([^)]*)\)', code):
            params_block = match.group(1).strip()
            if not params_block:
                continue
            for raw_param in params_block.split(','):
                param = re.sub(r'@\w+(?:\([^)]*\))?\s*', '', raw_param).strip()
                if not param:
                    continue
                parts = param.split()
                if len(parts) >= 2:
                    param_name = parts[-1]
                    param_type = ' '.join(parts[:-1])
                    param_types[param_name] = param_type

        for match in re.finditer(r'\b([A-Z]\w*)\s+([a-zA-Z_]\w*)\s*=', code):
            local_types[match.group(2)] = match.group(1)

        for match in re.finditer(rf'\b{entity_name}\s+([a-zA-Z_]\w*)\s*=', code):
            entity_variables.add(match.group(1))

        inferred_fields: Dict[str, str] = {}
        for match in re.finditer(r'([a-zA-Z_]\w*)\.\s*set([A-Z]\w*)\(([^;]+?)\);', code):
            target_variable = match.group(1)
            if entity_variables and target_variable not in entity_variables:
                continue
            field_name = self._lower_first(match.group(2))
            argument = match.group(3).strip()
            inferred_type = self._infer_java_type(argument, param_types, local_types)
            if field_name != 'id':
                inferred_fields[field_name] = inferred_type

        for match in re.finditer(r'([a-zA-Z_]\w*)\.\s*get([A-Z]\w*)\(\)', code):
            target_variable = match.group(1)
            if entity_variables and target_variable not in entity_variables:
                continue
            field_name = self._lower_first(match.group(2))
            if field_name != 'id' and field_name not in inferred_fields:
                inferred_fields[field_name] = self._infer_getter_type(field_name)

        preferred_order = ['customerId', 'productId', 'quantity', 'createdBy', 'status', 'createdAt', 'updatedAt']
        ordered_fields: List[Dict[str, str]] = []
        seen = set()
        for field_name in preferred_order:
            if field_name in inferred_fields:
                ordered_fields.append({'name': field_name, 'type': inferred_fields[field_name]})
                seen.add(field_name)
        for field_name, field_type in inferred_fields.items():
            if field_name not in seen:
                ordered_fields.append({'name': field_name, 'type': field_type})
        return ordered_fields

    def _infer_getter_type(self, field_name: str) -> str:
        """Infer type from getter-style field name when no setter provides it."""
        if field_name.lower().endswith('id'):
            return 'Long'
        if field_name.lower() in {'quantity', 'stock', 'count', 'total'}:
            return 'Integer'
        return 'String'

    def _infer_java_type(self, argument: str, param_types: Dict[str, str], local_types: Dict[str, str]) -> str:
        """Infer a Java type from a setter argument."""
        if argument in param_types:
            return param_types[argument]
        if argument in local_types:
            return local_types[argument]
        if 'LocalDateTime.now()' in argument:
            return 'LocalDateTime'
        if re.fullmatch(r'[A-Z]\w*', argument):
            return argument
        if any(operator in argument for operator in [' + ', ' - ', ' * ', ' / ']):
            return 'Integer'
        if argument.startswith('"') and argument.endswith('"'):
            return 'String'
        if re.fullmatch(r'\d+L', argument):
            return 'Long'
        if re.fullmatch(r'\d+', argument):
            return 'Integer'
        if argument in {'true', 'false'}:
            return 'Boolean'
        if '.toString()' in argument:
            return 'String'
        return 'String'

    def _generate_fallback_entity(self, entity_name: str, fields: Optional[List[Dict[str, str]]] = None) -> str:
        """Generate a fallback JPA entity aligned to generated service code."""
        fields = fields or []
        import_lines = ['import jakarta.persistence.*;']
        normalized_entity_name = self._normalize_entity_name(entity_name)
        if any(field['type'] == 'LocalDateTime' for field in fields):
            import_lines.append('import java.time.LocalDateTime;')
        if(entity_name in self.RESERVED_ENTITY_NAMES):
            entity_name += '_entity'
        field_blocks = []
        accessor_blocks = []
        for field in fields:
            field_name = field['name']
            field_type = field['type']
            if self._is_entity_reference_type(field_type):
                field_type = self._normalize_entity_name(field_type)
                field_blocks.append(
                    f"""    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "{self._to_snake_case(field_name)}_id")
    private {field_type} {field_name};"""
                )
            else:
                field_blocks.append(
                    f"""    @Column(name = "{self._to_snake_case(field_name)}")
    private {field_type} {field_name};"""
                )
            accessor_blocks.append(
                f"""    public {field_type} get{field_name[0].upper() + field_name[1:]}() {{
        return {field_name};
    }}

    public void set{field_name[0].upper() + field_name[1:]}({field_type} {field_name}) {{
        this.{field_name} = {field_name};
    }}"""
            )

        fields_section = '\n\n'.join(field_blocks)
        accessors_section = '\n\n'.join(accessor_blocks)
        if fields_section:
            fields_section = '\n\n' + fields_section
        if accessors_section:
            accessors_section = '\n\n' + accessors_section

        return f"""package {self.package_name}.entity;

{chr(10).join(import_lines)}

/**
 * Auto-generated fallback entity for {normalized_entity_name}.
 */
@Entity
@Table(name = "{entity_name.lower()}")
public class {normalized_entity_name} {{

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;{fields_section}

    public Long getId() {{
        return id;
    }}

    public void setId(Long id) {{
        this.id = id;
    }}{accessors_section}
}}
"""
    
    def generate_repositories(self, entities: Dict[str, str]) -> Dict[str, str]:
        """Generate JPA repository interfaces"""
        repositories = {}

        # Track existing repositories on disk to avoid duplicates.
        repo_dir = self.package_path / 'repository'
        existing_repo_names: Set[str] = set()
        if repo_dir.exists():
            for repo_file in repo_dir.glob('*.java'):
                existing_repo_names.add(repo_file.stem)
        existing_repo_names.update(self._existing_repositories)

        # Ensure repositories referenced in generated code exist.
        referenced_repo_names: Set[str] = set()
        for code in (getattr(self, "_latest_java_code", {}) or {}).values():
            for match in re.finditer(r'\b([A-Z]\w*)Repository\b', code):
                name = match.group(0)
                if name in {"JpaRepository", "CrudRepository"}:
                    continue
                referenced_repo_names.add(name)

        for filename, code in entities.items():
            # Generate repository name
            
            entity_name = filename.replace('.java', '')
            if entity_name in {"Jpa", "JpaRepository", "CrudRepository"}:
                continue
            repo_name = f"{entity_name}Repository.java"
            base_entity = entity_name[:-6] if entity_name.endswith("Entity") else entity_name
            if repo_name.replace('.java', '') in existing_repo_names:
                continue
            if f"{base_entity}Repository" in existing_repo_names:
                continue
            
            # Generate basic repository interface
            repo_content = self._generate_repository_interface(entity_name)
            repositories[repo_name] = repo_content

        # Generate missing repositories referenced by services/controllers.
        for repo_name in sorted(referenced_repo_names):
            if repo_name in {"JpaRepository", "CrudRepository"}:
                continue
            if repo_name in existing_repo_names or (repo_dir / f"{repo_name}.java").exists():
                continue
            base_entity = repo_name[:-10] if repo_name.endswith("Repository") else repo_name
            if base_entity in {"Jpa", "Crud", "Repository"}:
                continue
            if self._ddl_table_map:
                resolved_entity, _ = self._resolve_entity_from_ddl(base_entity, self._ddl_table_map)
            else:
                resolved_entity = base_entity
            resolved_entity = self._normalize_entity_name(resolved_entity)
            repositories[f"{repo_name}.java"] = self._generate_repository_interface(
                resolved_entity, repo_name=repo_name
            )
        # Write repositories to files
        for filename, code in repositories.items():
            file_path = repo_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
        
        logger.info(f"Generated {len(repositories)} repository interfaces")
        return repositories
    
    def _generate_repository_interface(self, entity_name: str, repo_name: Optional[str] = None) -> str:
        """Generate JPA repository interface"""
        interface_name = repo_name or f"{entity_name}Repository"
        return f"""package {self.package_name}.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import {self.package_name}.entity.{entity_name};

/**
 * JPA repository for {entity_name}
 */
@Repository
public interface {interface_name} extends JpaRepository<{entity_name}, Long> {{
    // Custom query methods can be added here
    // Example:
    // List<{entity_name}> findByName(String name);
}}
"""
    
    def generate_services(self, java_code: Dict[str, str]) -> Dict[str, str]:
        """Generate service layer classes"""
        services = {}
        
        for filename, code in java_code.items():
            class_name = None
            for line in code.splitlines():
                stripped = line.strip()
                if stripped.startswith('public class '):
                    class_name = stripped.split()[2]
                    break
            
            looks_like_service = (
                '@Service' in code
                or filename.lower().endswith('service.java')
                or (class_name is not None and class_name.lower().endswith('service'))
            )
            if looks_like_service:
                target_filename = f"{class_name}.java" if class_name else filename
                services[target_filename] = self._normalize_service_code(target_filename, code)
        
        # Write services to files
        service_dir = self.package_path / 'service'
        for filename, code in services.items():
            file_path = service_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
        
        logger.info(f"Generated {len(services)} service classes")
        return services
    
    def _normalize_service_code(self, filename: str, code: str) -> str:
        """Ensure generated service code has package/imports and @Service annotation."""
        service_name = filename.replace('.java', '')
        class_name = self._extract_class_name(code) or service_name
        entity_names = self._derive_entity_names(filename, class_name, code)
        repository_names: List[str] = []
        for match in re.finditer(r'\b([A-Z]\w*)Repository\b', code):
            raw_base = match.group(1)
            if self._ddl_table_map:
                resolved_entity, _ = self._resolve_entity_from_ddl(raw_base, self._ddl_table_map)
                resolved_entity = self._normalize_entity_name(resolved_entity)
                repo_base = resolved_entity[:-6] if resolved_entity.endswith("Entity") else resolved_entity
                repository_name = f"{repo_base}Repository"
            else:
                repository_name = f"{self._normalize_entity_name(raw_base)}Repository"
            if repository_name not in repository_names:
                repository_names.append(repository_name)

        import_lines = [
            'import org.springframework.beans.factory.annotation.Autowired;',
            'import org.springframework.stereotype.Service;',
            'import org.springframework.transaction.annotation.Transactional;',
        ]
        if 'LoggerFactory' in code or re.search(r'\bLogger\b', code):
            import_lines.append('import org.slf4j.Logger;')
            import_lines.append('import org.slf4j.LoggerFactory;')
        if 'DataAccessException' in code:
            import_lines.append('import org.springframework.dao.DataAccessException;')
        if 'LocalDateTime' in code:
            import_lines.append('import java.time.LocalDateTime;')
        if 'List<' in code:
            import_lines.append('import java.util.List;')
        if 'ArrayList' in code:
            import_lines.append('import java.util.ArrayList;')
        if 'Arrays.' in code or 'Arrays ' in code:
            import_lines.append('import java.util.Arrays;')
        if 'Collections.' in code:
            import_lines.append('import java.util.Collections;')
        if 'Objects.' in code:
            import_lines.append('import java.util.Objects;')
        if 'Pattern.' in code:
            import_lines.append('import java.util.regex.Pattern;')
        for entity_name in entity_names:
            if self._ddl_table_map:
                normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, self._ddl_table_map)
            else:
                normalized_entity = entity_name
            normalized_entity = self._normalize_entity_name(normalized_entity)
            import_lines.append(f'import {self.package_name}.entity.{normalized_entity};')
        for repository_name in repository_names:
            import_lines.append(f'import {self.package_name}.repository.{repository_name};')
        import_lines.append(f'import {self.package_name}.exception.BusinessException;')
        imports = '\n'.join(dict.fromkeys(import_lines))

        body = code.strip()
        for entity_name in entity_names:
            if self._ddl_table_map:
                normalized_entity_name, _ = self._resolve_entity_from_ddl(entity_name, self._ddl_table_map)
            else:
                normalized_entity_name = entity_name
            normalized_entity_name = self._normalize_entity_name(normalized_entity_name)
            if normalized_entity_name != entity_name:
                repo_base = normalized_entity_name[:-6] if normalized_entity_name.endswith("Entity") else normalized_entity_name
                body = re.sub(
                    rf'\\b{re.escape(entity_name)}Repository\\b',
                    f'{repo_base}Repository',
                    body,
                )
                body = re.sub(
                    rf'\\b{re.escape(entity_name)}\\b(?!Repository)',
                    normalized_entity_name,
                    body,
                )
        body = body.replace("OrderProcessingException", "BusinessException")
        body = body.replace("catch (IllegalArgumentException ", "catch (java.lang.IllegalArgumentException ")
        body = body.replace("throw new IllegalArgumentException(", "throw new java.lang.IllegalArgumentException(")
        if '@Service' not in body:
            body = body.replace(f"public class {service_name}", f"@Service\npublic class {service_name}")
            if class_name != service_name:
                body = body.replace(f"public class {class_name}", f"@Service\npublic class {class_name}")
        body = self._ensure_process_result_class(body)

        if 'package ' in body:
            package_match = re.match(r'(package\s+[^\n]+;\s*)', body)
            if package_match:
                package_line = package_match.group(1).strip()
                remainder = body[package_match.end():].lstrip()
                return f"""{package_line}

{imports}

{remainder}
"""

        return f"""package {self.package_name}.service;

{imports}
{body}
"""

    def _normalize_controller_code(self, filename: str, code: str) -> str:
        """Ensure controller code uses resolved entity names and imports."""
        controller_name = self._extract_type_name(code) or filename.replace('.java', '')
        body_lines = [
            line for line in code.splitlines()
            if not line.strip().startswith('package ')
            and not line.strip().startswith('import ')
        ]
        body = '\n'.join(body_lines).strip()

        import_lines = [
            'import org.springframework.web.bind.annotation.*;',
            'import org.springframework.http.ResponseEntity;',
        ]
        if 'List<' in code:
            import_lines.append('import java.util.List;')

        # Collect entity type usages from imports and method signatures.
        entity_candidates: Set[str] = set()
        for match in re.finditer(r'import\s+[^;]*\.entity\.([A-Z]\w+);', code):
            entity_candidates.add(match.group(1))
        for match in re.finditer(r'ResponseEntity<\s*([A-Z]\w+)\s*>', body):
            entity_candidates.add(match.group(1))
        for match in re.finditer(r'@RequestBody\s+([A-Z]\w+)', body):
            entity_candidates.add(match.group(1))

        for entity_name in sorted(entity_candidates):
            if self._ddl_table_map:
                resolved_entity, _ = self._resolve_entity_from_ddl(entity_name, self._ddl_table_map)
            else:
                resolved_entity = entity_name
            resolved_entity = self._normalize_entity_name(resolved_entity)
            import_lines.append(f'import {self.package_name}.entity.{resolved_entity};')
            if resolved_entity != entity_name:
                body = re.sub(
                    rf'\\b{re.escape(entity_name)}\\b(?!Controller|Service|Repository)',
                    resolved_entity,
                    body,
                )

        import_lines = list(dict.fromkeys(import_lines))
        imports = '\n'.join(import_lines)

        return f"""package {self.package_name}.controller;

{imports}

{body}
"""

    def _normalize_repository_code(
        self,
        filename: str,
        code: str,
        ddl_map: Optional[Dict[str, str]] = None,
    ) -> str:
        """Ensure repository code has package/imports and @Repository annotation."""
        type_name = self._extract_type_name(code) or filename.replace('.java', '')
        if type_name in {'JpaRepository', 'CrudRepository'}:
            return code

        import_lines = [
            'import org.springframework.stereotype.Repository;',
        ]
        if 'JpaRepository' in code:
            import_lines.append('import org.springframework.data.jpa.repository.JpaRepository;')
        if 'CrudRepository' in code:
            import_lines.append('import org.springframework.data.repository.CrudRepository;')
        if '@Query' in code or 'Query(' in code:
            import_lines.append('import org.springframework.data.jpa.repository.Query;')
        if '@Param' in code:
            import_lines.append('import org.springframework.data.repository.query.Param;')
        if '@Modifying' in code:
            import_lines.append('import org.springframework.data.jpa.repository.Modifying;')
        if '@Transactional' in code:
            import_lines.append('import org.springframework.transaction.annotation.Transactional;')
        if 'List<' in code:
            import_lines.append('import java.util.List;')
        if 'Optional<' in code:
            import_lines.append('import java.util.Optional;')
        if 'LocalDateTime' in code:
            import_lines.append('import java.time.LocalDateTime;')
        if 'LocalTime' in code:
            import_lines.append('import java.time.LocalTime;')
        if 'BigDecimal' in code:
            import_lines.append('import java.math.BigDecimal;')
        if 'List<' in code:
            import_lines.append('import java.util.List;')
        if 'ArrayList' in code:
            import_lines.append('import java.util.ArrayList;')
        if 'Collections.' in code:
            import_lines.append('import java.util.Collections;')
        if 'Pattern' in code:
            import_lines.append('import java.util.regex.Pattern;')
        if 'Optional' in code:
            import_lines.append('import java.util.Optional;')

        entity_matches = re.findall(
            r'extends\s+(?:JpaRepository|CrudRepository)\s*<\s*([A-Za-z_][\w$#]*)',
            code,
        )
        ddl_map = ddl_map or {}
        for entity_name in entity_matches:
            if ddl_map:
                normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, ddl_map)
            else:
                normalized_entity = self._normalize_entity_type_name(entity_name)
            normalized_entity = self._normalize_entity_name(normalized_entity)
            import_lines.append(f'import {self.package_name}.entity.{normalized_entity};')

        imports = '\n'.join(dict.fromkeys(import_lines))

        # Normalize entity type usage directly in the extends clause to avoid lowercase mismatches.
        for entity_name in entity_matches:
            if ddl_map:
                normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, ddl_map)
            else:
                normalized_entity = self._normalize_entity_type_name(entity_name)
            normalized_entity = self._normalize_entity_name(normalized_entity)
            code = re.sub(
                rf'(extends\s+(?:JpaRepository|CrudRepository)\s*<\s*){re.escape(entity_name)}(\s*,)',
                lambda match, entity=normalized_entity: f"{match.group(1)}{entity}{match.group(2)}",
                code,
            )

        body_lines = [
            line for line in code.splitlines()
            if not line.strip().startswith('package ')
            and not line.strip().startswith('import ')
        ]
        body = '\n'.join(body_lines).strip()
        for entity_name in entity_matches:
            if ddl_map:
                normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, ddl_map)
            else:
                normalized_entity = self._normalize_entity_type_name(entity_name)
            normalized_entity = self._normalize_entity_name(normalized_entity)
            if normalized_entity != entity_name:
                body = re.sub(rf'\\b{re.escape(entity_name)}\\b', normalized_entity, body)
        if '@Repository' not in body:
            body = re.sub(r'public\s+interface', '@Repository\npublic interface', body, count=1)

        # If the repository body is truncated (unbalanced delimiters), drop the trailing fragment.
        if body.count('(') > body.count(')') or body.count('{') > body.count('}'):
            cut_idx = max(body.rfind('\n    @Query'), body.rfind('\n    @Modifying'), body.rfind('\n    @Transactional'))
            if cut_idx > 0:
                body = body[:cut_idx].rstrip()
            if not body.endswith('}'):
                body = body.rstrip() + "\n}\n"

        return f"""package {self.package_name}.repository;

{imports}

{body}
"""

    def _normalize_entity_code(self, filename: str, code: str) -> str:
        """Ensure entity code has package/imports and @Entity annotation."""
        type_name = self._extract_type_name(code) or filename.replace('.java', '')
        import_lines = []
        if 'jakarta.persistence.' in code or 'javax.persistence.' in code:
            import_lines.append('import jakarta.persistence.*;')
        else:
            import_lines.append('import jakarta.persistence.*;')
        if 'LocalDateTime' in code:
            import_lines.append('import java.time.LocalDateTime;')
        if 'List<' in code:
            import_lines.append('import java.util.List;')
        if 'Set<' in code:
            import_lines.append('import java.util.Set;')

        imports = '\n'.join(dict.fromkeys(import_lines))

        body_lines = [
            line for line in code.splitlines()
            if not line.strip().startswith('package ')
            and not line.strip().startswith('import ')
        ]
        body = '\n'.join(body_lines).strip()
        if '@Entity' not in body and any(token in body for token in ('@Id', '@Column', '@Table')):
            body = re.sub(r'public\s+class', '@Entity\npublic class', body, count=1)
        if '@Entity' not in body and f"public class {type_name}" in body:
            body = body.replace(f"public class {type_name}", f"@Entity\npublic class {type_name}")

        return f"""package {self.package_name}.entity;

{imports}

{body}
"""

    def _entity_has_meaningful_fields(self, code: str) -> bool:
        """Check if an entity has fields beyond an id."""
        field_lines = [
            line for line in code.splitlines()
            if line.strip().startswith("private ")
        ]
        if not field_lines:
            return False
        non_id_fields = [
            line for line in field_lines
            if " id;" not in line.lower()
        ]
        return len(non_id_fields) > 0

    def _map_sql_type_to_java(self, sql_type: str) -> str:
        normalized = sql_type.upper()
        if normalized.startswith(("VARCHAR", "CHAR", "CLOB", "NCLOB", "NVARCHAR")):
            return "String"
        if normalized.startswith("NUMBER"):
            if "," in normalized:
                return "BigDecimal"
            return "Long"
        if normalized.startswith(("INT", "INTEGER", "SMALLINT", "BIGINT")):
            return "Long"
        if normalized.startswith(("DATE", "TIMESTAMP")):
            return "LocalDateTime"
        if normalized.startswith(("FLOAT", "DOUBLE", "REAL")):
            return "Double"
        if normalized.startswith(("DECIMAL", "NUMERIC")):
            return "BigDecimal"
        return "String"

    def _generate_entity_from_ddl(
        self,
        entity_name: str,
        table_name: str,
        columns: List[Dict[str, str]],
    ) -> str:
        """Generate a JPA entity from DDL columns."""
        import_lines = ['import jakarta.persistence.*;']
        field_lines = []
        accessor_lines = []

        id_column = None
        for col in columns:
            if col["name"].upper() == "ID":
                id_column = col["name"]
                break
        if not id_column:
            for col in columns:
                if col["name"].upper().endswith("_ID"):
                    id_column = col["name"]
                    break
        if not id_column and columns:
            id_column = columns[0]["name"]

        for col in columns:
            col_name = col["name"].upper()
            java_type = self._map_sql_type_to_java(col.get("type", ""))
            if java_type == "LocalDateTime":
                import_lines.append("import java.time.LocalDateTime;")
            if java_type == "BigDecimal":
                import_lines.append("import java.math.BigDecimal;")

            field_name = self._to_lower_camel_case(col_name)
            annotations = []
            if col_name == id_column:
                annotations.append("@Id")
                if self._is_numeric_type(col.get("type", "")):
                    annotations.append("@GeneratedValue(strategy = GenerationType.IDENTITY)")
            annotations.append(f'@Column(name = "{col_name}")')
            field_lines.append("\n".join(annotations))
            field_lines.append(f"    private {java_type} {field_name};\n")

            accessor_lines.append(
                f"""    public {java_type} get{self._capitalize_first(field_name)}() {{
        return {field_name};
    }}

    public void set{self._capitalize_first(field_name)}({java_type} {field_name}) {{
        this.{field_name} = {field_name};
    }}
"""
            )

        imports = "\n".join(dict.fromkeys(import_lines))
        fields_block = "\n".join(field_lines).rstrip()
        accessors_block = "\n".join(accessor_lines).rstrip()

        return f"""package {self.package_name}.entity;

{imports}

@Entity
@Table(name = "{table_name}")
public class {entity_name} {{

{fields_block}

{accessors_block}
}}
"""

    def _lower_first(self, value: str) -> str:
        """Lowercase the first character of a string."""
        if not value:
            return value
        return value[0].lower() + value[1:]

    def _capitalize_first(self, value: str) -> str:
        """Uppercase the first character of a string."""
        if not value:
            return value
        return value[0].upper() + value[1:]

    def _to_lower_camel_case(self, value: str) -> str:
        """Convert uppercase/snake_case to lowerCamelCase."""
        if not value:
            return value
        pascal = self._to_camel_case(value)
        return self._lower_first(pascal)

    def _is_numeric_type(self, sql_type: str) -> bool:
        normalized = (sql_type or "").upper()
        return normalized.startswith(("NUMBER", "INT", "INTEGER", "SMALLINT", "BIGINT", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL"))

    def _ensure_process_result_class(self, body: str) -> str:
        """Inject a nested ProcessOrderResult class when service code references it but does not define it."""
        if 'ProcessOrderResult' not in body or 'class ProcessOrderResult' in body:
            return body
        marker = '\n}'
        nested_class = """

    public static class ProcessOrderResult {
        private final Long orderId;
        private final String status;

        public ProcessOrderResult(Long orderId, String status) {
            this.orderId = orderId;
            this.status = status;
        }

        public Long getOrderId() {
            return orderId;
        }

        public String getStatus() {
            return status;
        }
    }
"""
        if marker in body:
            return body[::-1].replace(marker[::-1], (nested_class + '\n}')[::-1], 1)[::-1]
        return body + nested_class

    def _to_snake_case(self, value: str) -> str:
        """Convert camelCase or PascalCase to snake_case."""
        if not value:
            return value
        return re.sub(r'(?<!^)(?=[A-Z])', '_', value).lower()

    def _is_entity_reference_type(self, field_type: str) -> bool:
        """Detect when a fallback field type should be emitted as a JPA entity relationship."""
        scalar_types = {
            'String',
            'Long',
            'Integer',
            'Boolean',
            'Double',
            'Float',
            'BigDecimal',
            'LocalDate',
            'LocalDateTime',
            'Instant',
            'UUID',
        }
        return bool(field_type) and field_type not in scalar_types and field_type[:1].isupper()
    
    def generate_controllers(self, services: Dict[str, str]) -> Dict[str, str]:
        """Generate REST controller classes"""
        controllers = {}
        
        for filename, code in services.items():
            # Generate controller name from service name
            service_name = filename.replace('.java', '')
            if service_name.endswith('Service'):
                controller_name = service_name[:-7] + 'Controller.java'
            else:
                controller_name = service_name + 'Controller.java'
            
            # Generate basic controller
            if 'processOrder(' in code:
                controller_content = self._generate_process_controller(service_name)
            else:
                controller_content = self._generate_controller(service_name, code)
            if not controller_content:
                continue
            controllers[controller_name] = controller_content
        
        # Write controllers to files
        controller_dir = self.package_path / 'controller'
        for filename, code in controllers.items():
            file_path = controller_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
        
        logger.info(f"Generated {len(controllers)} controller classes")
        return controllers
    
    def _service_has_method(self, code: str, method_name: str) -> bool:
        pattern = rf"\b{re.escape(method_name)}\s*\("
        return bool(re.search(pattern, code))

    def _extract_public_methods(self, code: str) -> List[Tuple[str, str, str]]:
        methods: List[Tuple[str, str, str]] = []
        for match in re.finditer(
            r'public\s+([A-Za-z_][\w<>, ?]+)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)',
            code,
        ):
            return_type, name, params = match.groups()
            methods.append((return_type.strip(), name.strip(), params.strip()))
        return methods

    def _generate_controller(self, service_name: str, service_code: str) -> str:
        """Generate REST controller"""
        entity_name = service_name.replace('Service', '')
        if self._ddl_table_map:
            resolved_entity_name, _ = self._resolve_entity_from_ddl(entity_name, self._ddl_table_map)
        else:
            resolved_entity_name = entity_name
        resolved_entity_name = self._normalize_entity_name(resolved_entity_name)
        service_var = service_name[0].lower() + service_name[1:]

        has_get_all = self._service_has_method(service_code, 'getAll')
        has_get_by_id = self._service_has_method(service_code, 'getById')
        has_create = self._service_has_method(service_code, 'create')
        has_update = self._service_has_method(service_code, 'update')
        has_delete = self._service_has_method(service_code, 'delete')

        if not any([has_get_all, has_get_by_id, has_create, has_update, has_delete]):
            public_methods = [
                method for method in self._extract_public_methods(service_code)
                if method[1] != service_name
            ]
            if not public_methods:
                return ""
            return_type, method_name, params = public_methods[0]
            if return_type == "void":
                return_type = "Void"
            params = params.strip()
            param_block = ""
            call_args = ""
            extra_imports = []
            if params:
                parts = [p.strip() for p in params.split(",") if p.strip()]
                if len(parts) == 1:
                    param_type, param_name = parts[0].rsplit(" ", 1)
                    param_block = f"@RequestBody {param_type} {param_name}"
                    call_args = param_name
                else:
                    return ""
            return_statement = (
                f"return ResponseEntity.ok({service_var}.{method_name}({call_args}));"
                if return_type != "void"
                else f"{service_var}.{method_name}({call_args});\n        return ResponseEntity.noContent().build();"
            )
            import_lines = [
                'import org.springframework.beans.factory.annotation.Autowired;',
                'import org.springframework.http.ResponseEntity;',
                'import org.springframework.web.bind.annotation.*;',
                f'import {self.package_name}.service.{service_name};',
            ]
            import_lines.extend(extra_imports)
            imports = "\n".join(import_lines)
            method_block = f"""    @PostMapping
    public ResponseEntity<{return_type}> {method_name}({param_block}) {{
        {return_statement}
    }}"""
            return f"""package {self.package_name}.controller;

{imports}

@RestController
@RequestMapping("/api/{entity_name.lower()}")
public class {entity_name}Controller {{

    @Autowired
    private {service_name} {service_var};

{method_block}
}}
"""

        import_lines = [
            'import org.springframework.beans.factory.annotation.Autowired;',
            'import org.springframework.http.ResponseEntity;',
            'import org.springframework.web.bind.annotation.*;',
            f'import {self.package_name}.service.{service_name};',
            f'import {self.package_name}.entity.{resolved_entity_name};',
        ]
        if has_get_all:
            import_lines.append('import java.util.List;')
        imports = '\\n'.join(import_lines)

        methods = []
        if has_get_all:
            methods.append(
                f"""    @GetMapping
    public ResponseEntity<List<{resolved_entity_name}>> getAll{entity_name}s() {{
        List<{resolved_entity_name}> {entity_name.lower()}s = {service_var}.getAll();
        return ResponseEntity.ok({entity_name.lower()}s);
    }}"""
            )
        if has_get_by_id:
            methods.append(
                f"""    @GetMapping("/{{id}}")
    public ResponseEntity<{resolved_entity_name}> get{entity_name}ById(@PathVariable Long id) {{
        {resolved_entity_name} {entity_name.lower()} = {service_var}.getById(id);
        return ResponseEntity.ok({entity_name.lower()});
    }}"""
            )
        if has_create:
            methods.append(
                f"""    @PostMapping
    public ResponseEntity<{resolved_entity_name}> create{entity_name}(@RequestBody {resolved_entity_name} {entity_name.lower()}) {{
        {resolved_entity_name} created{entity_name} = {service_var}.create({entity_name.lower()});
        return ResponseEntity.ok(created{entity_name});
    }}"""
            )
        if has_update:
            methods.append(
                f"""    @PutMapping("/{{id}}")
    public ResponseEntity<{resolved_entity_name}> update{entity_name}(
            @PathVariable Long id,
            @RequestBody {resolved_entity_name} {entity_name.lower()}) {{
        {resolved_entity_name} updated{entity_name} = {service_var}.update(id, {entity_name.lower()});
        return ResponseEntity.ok(updated{entity_name});
    }}"""
            )
        if has_delete:
            methods.append(
                f"""    @DeleteMapping("/{{id}}")
    public ResponseEntity<Void> delete{entity_name}(@PathVariable Long id) {{
        {service_var}.delete(id);
        return ResponseEntity.noContent().build();
    }}"""
            )

        methods_block = "\\n\\n".join(methods)

        return f"""package {self.package_name}.controller;

{imports}

/**
 * REST controller for {entity_name} operations
 */
@RestController
@RequestMapping("/api/{entity_name.lower()}")
public class {entity_name}Controller {{
    
    @Autowired
    private {service_name} {service_var};
    
{methods_block}
}}
"""

    def _generate_process_controller(self, service_name: str) -> str:
        """Generate controller for services that expose processOrder method."""
        entity_name = service_name.replace('Service', '')
        return f"""package {self.package_name}.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import {self.package_name}.service.{service_name};

/**
 * REST controller for {entity_name} process operations
 */
@RestController
@RequestMapping("/api/{entity_name.lower()}")
public class {entity_name}Controller {{
    
    @Autowired
    private {service_name} {service_name[0].lower() + service_name[1:]};
    
    @PostMapping("/process")
    public ResponseEntity<Object> processOrder(
            @RequestParam Long customerId,
            @RequestParam Long productId,
            @RequestParam Integer quantity,
            @RequestParam String createdBy) {{
        return ResponseEntity.ok(
                {service_name[0].lower() + service_name[1:]}.processOrder(customerId, productId, quantity, createdBy)
        );
    }}
}}
"""


def create_spring_boot_generator(config: Dict[str, Any]) -> SpringBootGenerator:
    """Create and return a configured Spring Boot generator"""
    return SpringBootGenerator(config)
