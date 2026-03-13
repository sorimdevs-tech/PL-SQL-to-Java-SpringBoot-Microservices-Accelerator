"""
Configuration management for PL/SQL Modernization Platform
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv


class LLMConfig(BaseModel):
    """LLM configuration settings"""
    provider: str = "openai"
    model: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4000
    timeout: int = 60
    retry_attempts: int = 3
    batch_size: int = 5
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if v is None:
            # Try to get from environment variables
            v = (
                os.getenv('OPENAI_API_KEY')
                or os.getenv('ANTHROPIC_API_KEY')
                or os.getenv('OPENROUTER_API_KEY')
            )
        if v is None:
            raise ValueError("API key must be provided either in config or environment variables")
        return v


class DatabaseConfig(BaseModel):
    """Database configuration settings"""
    type: str = "oracle"
    connection_string: Optional[str] = None
    query_timeout: int = 30
    max_connections: int = 10


class OutputConfig(BaseModel):
    """Output configuration settings"""
    project_name: str = "converted-app"
    group_id: str = "com.company"
    artifact_id: str = "converted-app"
    package_name: str = "com.company.project"
    description: str = "PL/SQL to Java Modernization Project"
    target_directory: str = "./output"
    java_version: str = "17"
    spring_boot_version: str = "3.1.0"
    build_tool: str = "maven"
    packaging: str = "jar"
    config_format: str = "properties"
    generate_tests: bool = True
    generate_docs: bool = True
    format_code: bool = True


class ValidationConfig(BaseModel):
    """Validation configuration settings"""
    enable_sql_validation: bool = True
    enable_unit_tests: bool = True
    test_containers: bool = True
    validation_timeout: int = 120
    compare_results: bool = True


class PerformanceConfig(BaseModel):
    """Performance configuration settings"""
    parallel_processing: bool = True
    max_workers: int = 4
    cache_llm_responses: bool = True
    cache_ttl: int = 3600
    memory_limit: str = "2GB"


class SecurityConfig(BaseModel):
    """Security configuration settings"""
    mask_sensitive_data: bool = True
    validate_generated_code: bool = True
    restrict_llm_context: bool = True
    sanitize_inputs: bool = True


class EnterpriseConfig(BaseModel):
    """Enterprise configuration settings"""
    microservices: bool = False
    message_queue: str = "kafka"
    queue_config: Dict[str, Any] = {}
    monitoring: Dict[str, Any] = {}


class TemplatesConfig(BaseModel):
    """Templates configuration settings"""
    entity_template: str = "templates/java/entity.java.j2"
    repository_template: str = "templates/java/repository.java.j2"
    service_template: str = "templates/java/service.java.j2"
    controller_template: str = "templates/java/controller.java.j2"
    application_config: str = "templates/spring-boot/application.yml.j2"
    pom_template: str = "templates/spring-boot/pom.xml.j2"


class LoggingConfig(BaseModel):
    """Logging configuration settings"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_logging: bool = True
    log_file: str = "./logs/modernization.log"
    max_log_size: str = "10MB"
    backup_count: int = 5


class PlatformConfig(BaseModel):
    """Main platform configuration"""
    llm: LLMConfig = LLMConfig()
    database: DatabaseConfig = DatabaseConfig()
    output: OutputConfig = OutputConfig()
    validation: ValidationConfig = ValidationConfig()
    performance: PerformanceConfig = PerformanceConfig()
    security: SecurityConfig = SecurityConfig()
    enterprise: EnterpriseConfig = EnterpriseConfig()
    templates: TemplatesConfig = TemplatesConfig()
    logging: LoggingConfig = LoggingConfig()


class ConfigManager:
    """Configuration manager for the platform"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize configuration manager
        
        Args:
            config_path (str): Path to configuration file
        """
        self.config_path = Path(config_path)
        self.config: Optional[PlatformConfig] = None
        self._load_dotenv()

    def _load_dotenv(self):
        """Load .env from project root if present."""
        env_path = self.config_path.parent / ".env"
        load_dotenv(dotenv_path=env_path, override=False)
        
    def load_config(self) -> PlatformConfig:
        """
        Load configuration from file
        
        Returns:
            PlatformConfig: Loaded configuration
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            # Load environment variables for sensitive data
            self._load_environment_variables(config_data)
            
            # Validate and parse configuration
            self.config = PlatformConfig(**config_data)
            
            # Setup logging
            self._setup_logging()
            
            return self.config
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    def _load_environment_variables(self, config_data: Dict[str, Any]):
        """
        Load sensitive configuration from environment variables
        
        Args:
            config_data (Dict[str, Any]): Configuration data to update
        """
        # Load API keys from environment
        llm_config = config_data.get('llm', {})
        llm_api_key = self._resolve_env_placeholder(llm_config.get('api_key'))
        llm_config['api_key'] = llm_api_key
        if llm_api_key in (None, "", "your-api-key-here"):
            api_key = (
                os.getenv('OPENAI_API_KEY')
                or os.getenv('ANTHROPIC_API_KEY')
                or os.getenv('OPENROUTER_API_KEY')
            )
            if api_key:
                llm_config['api_key'] = api_key
                config_data['llm'] = llm_config

        fallback_cfg = llm_config.get('fallback')
        if isinstance(fallback_cfg, dict):
            fallback_cfg['api_key'] = self._resolve_env_placeholder(fallback_cfg.get('api_key'))
            llm_config['fallback'] = fallback_cfg
            config_data['llm'] = llm_config
        
        # Load database connection string from environment
        db_config = config_data.get('database', {})
        db_conn = db_config.get('connection_string')
        if db_conn in (None, "", "oracle://user:pass@host:port/service"):
            db_connection = os.getenv('DATABASE_CONNECTION_STRING')
            if db_connection:
                db_config['connection_string'] = db_connection
                config_data['database'] = db_config

    def _resolve_env_placeholder(self, value: Optional[str]) -> Optional[str]:
        """Resolve ${ENV_VAR} placeholders from the current environment."""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_key_name = value[2:-1].strip()
            return os.getenv(env_key_name)
        return value
    
    def _setup_logging(self):
        """Setup logging based on configuration"""
        import logging
        import logging.config
        
        if self.config and self.config.logging.file_logging:
            # Create logs directory if it doesn't exist
            log_file = Path(self.config.logging.log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Configure logging
            logging_config = {
                'version': 1,
                'disable_existing_loggers': False,
                'formatters': {
                    'standard': {
                        'format': self.config.logging.format
                    },
                },
                'handlers': {
                    'default': {
                        'level': self.config.logging.level,
                        'formatter': 'standard',
                        'class': 'logging.StreamHandler',
                    },
                    'file': {
                        'level': self.config.logging.level,
                        'formatter': 'standard',
                        'class': 'logging.handlers.RotatingFileHandler',
                        'filename': self.config.logging.log_file,
                        'maxBytes': self._parse_size(self.config.logging.max_log_size),
                        'backupCount': self.config.logging.backup_count,
                        'encoding': 'utf8',
                    },
                },
                'loggers': {
                    '': {  # root logger
                        'handlers': ['default', 'file'],
                        'level': self.config.logging.level,
                        'propagate': False
                    }
                }
            }
            
            logging.config.dictConfig(logging_config)
    
    def _parse_size(self, size_str: str) -> int:
        """
        Parse size string to bytes
        
        Args:
            size_str (str): Size string (e.g., "10MB", "1GB")
            
        Returns:
            int: Size in bytes
        """
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key
        
        Args:
            key (str): Configuration key (e.g., "llm.model", "output.package_name")
            default: Default value if key not found
            
        Returns:
            Any: Configuration value
        """
        if not self.config:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        
        # Navigate through nested configuration
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
        
        return value
    
    def update(self, updates: Dict[str, Any]):
        """
        Update configuration with new values
        
        Args:
            updates (Dict[str, Any]): Configuration updates
        """
        if not self.config:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        
        # Convert dict to PlatformConfig and merge
        update_config = PlatformConfig(**updates)
        self._merge_config(self.config, update_config)
    
    def _merge_config(self, base: PlatformConfig, update: PlatformConfig):
        """
        Recursively merge configuration objects
        
        Args:
            base (PlatformConfig): Base configuration
            update (PlatformConfig): Update configuration
        """
        for field in base.__fields__.keys():
            if hasattr(update, field):
                update_value = getattr(update, field)
                if isinstance(update_value, BaseModel):
                    self._merge_config(getattr(base, field), update_value)
                else:
                    setattr(base, field, update_value)
    
    def save(self, path: Optional[str] = None):
        """
        Save current configuration to file
        
        Args:
            path (Optional[str]): Path to save configuration (defaults to original path)
        """
        if not self.config:
            raise RuntimeError("No configuration to save")
        
        save_path = Path(path) if path else self.config_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict and save
        config_dict = self.config.dict()
        
        # Remove sensitive data before saving
        if 'llm' in config_dict and 'api_key' in config_dict['llm']:
            config_dict['llm']['api_key'] = "your-api-key-here"
        
        with open(save_path, 'w') as f:
            json.dump(config_dict, f, indent=2)


def load_config(config_path: str = "config.json") -> PlatformConfig:
    """
    Load configuration from file
    
    Args:
        config_path (str): Path to configuration file
        
    Returns:
        PlatformConfig: Loaded configuration
    """
    config_manager = ConfigManager(config_path)
    return config_manager.load_config()


def get_config_value(key: str, default: Any = None, config_path: str = "config.json") -> Any:
    """
    Get a specific configuration value
    
    Args:
        key (str): Configuration key
        default: Default value if key not found
        config_path (str): Path to configuration file
        
    Returns:
        Any: Configuration value
    """
    config_manager = ConfigManager(config_path)
    config_manager.load_config()
    return config_manager.get(key, default)
