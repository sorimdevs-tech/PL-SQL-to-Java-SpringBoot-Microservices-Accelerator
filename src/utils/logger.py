"""
Logging utilities for PL/SQL Modernization Platform
"""

import logging
import sys
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme


# Custom theme for rich logging
CUSTOM_THEME = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "success": "bold green",
    "debug": "dim blue",
})


def setup_logging(level: int = logging.INFO, use_rich: bool = True, 
                 log_file: Optional[str] = None):
    """
    Setup logging configuration for the platform
    
    Args:
        level (int): Logging level (default: INFO)
        use_rich (bool): Use rich formatting for console output
        log_file (Optional[str]): File to write logs to
    """
    # Create custom formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with rich formatting
    if use_rich:
        console = Console(theme=CUSTOM_THEME)
        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
            show_path=True
        )
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    else:
        # Standard console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        from logging.handlers import RotatingFileHandler
        
        # Create directory if it doesn't exist
        import os
        from pathlib import Path
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Set specific log levels for noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    # Log platform startup
    logger.info("PL/SQL Modernization Platform logging initialized")
    logger.debug(f"Logging level set to: {logging.getLevelName(level)}")


class ProgressLogger:
    """Utility class for logging progress with rich formatting"""
    
    def __init__(self, logger_name: str = __name__):
        """
        Initialize progress logger
        
        Args:
            logger_name (str): Name of the logger
        """
        self.logger = logging.getLogger(logger_name)
        self.console = Console(theme=CUSTOM_THEME)
    
    def start_stage(self, stage_name: str, description: str = ""):
        """
        Log the start of a processing stage
        
        Args:
            stage_name (str): Name of the stage
            description (str): Optional description
        """
        msg = f"🚀 Starting Stage: {stage_name}"
        if description:
            msg += f" - {description}"
        self.logger.info(msg)
    
    def end_stage(self, stage_name: str, success: bool = True, details: str = ""):
        """
        Log the end of a processing stage
        
        Args:
            stage_name (str): Name of the stage
            success (bool): Whether the stage completed successfully
            details (str): Optional details about the result
        """
        status = "✅" if success else "❌"
        msg = f"{status} Completed Stage: {stage_name}"
        if details:
            msg += f" - {details}"
        self.logger.info(msg)
    
    def progress_update(self, message: str, progress: Optional[int] = None, 
                       total: Optional[int] = None):
        """
        Log a progress update
        
        Args:
            message (str): Progress message
            progress (Optional[int]): Current progress
            total (Optional[int]): Total progress
        """
        if progress is not None and total is not None:
            percentage = (progress / total) * 100
            msg = f"📊 {message} ({progress}/{total} - {percentage:.1f}%)"
        else:
            msg = f"📊 {message}"
        self.logger.info(msg)
    
    def warning_with_context(self, message: str, context: Optional[Dict] = None):
        """
        Log a warning with additional context
        
        Args:
            message (str): Warning message
            context (Optional[Dict]): Additional context information
        """
        if context:
            import json
            context_str = json.dumps(context, indent=2)
            full_message = f"{message}\nContext:\n{context_str}"
        else:
            full_message = message
        self.logger.warning(full_message)
    
    def error_with_traceback(self, message: str, exc_info: bool = True):
        """
        Log an error with traceback information
        
        Args:
            message (str): Error message
            exc_info (bool): Include exception info in traceback
        """
        self.logger.error(message, exc_info=exc_info)
    
    def success(self, message: str):
        """
        Log a success message
        
        Args:
            message (str): Success message
        """
        self.logger.info(f"🎉 {message}")
    
    def debug_with_data(self, message: str, data: Any):
        """
        Log debug information with data
        
        Args:
            message (str): Debug message
            data (Any): Data to log (will be converted to string)
        """
        import json
        try:
            data_str = json.dumps(data, indent=2, default=str)
        except (TypeError, ValueError):
            data_str = str(data)
        
        full_message = f"{message}:\n{data_str}"
        self.logger.debug(full_message)


class PerformanceLogger:
    """Utility class for logging performance metrics"""
    
    def __init__(self, logger_name: str = __name__):
        """
        Initialize performance logger
        
        Args:
            logger_name (str): Name of the logger
        """
        self.logger = logging.getLogger(logger_name)
    
    def log_execution_time(self, operation: str, duration: float):
        """
        Log execution time for an operation
        
        Args:
            operation (str): Name of the operation
            duration (float): Duration in seconds
        """
        if duration > 60:
            time_str = f"{duration/60:.2f} minutes"
        elif duration > 1:
            time_str = f"{duration:.2f} seconds"
        else:
            time_str = f"{duration*1000:.1f} milliseconds"
        
        self.logger.info(f"⏱️ {operation} completed in {time_str}")
    
    def log_memory_usage(self, operation: str, memory_mb: float):
        """
        Log memory usage for an operation
        
        Args:
            operation (str): Name of the operation
            memory_mb (float): Memory usage in megabytes
        """
        self.logger.info(f"💾 {operation} used {memory_mb:.2f} MB of memory")
    
    def log_cache_hit(self, cache_type: str, key: str):
        """
        Log a cache hit
        
        Args:
            cache_type (str): Type of cache (e.g., "LLM", "Parsing")
            key (str): Cache key
        """
        self.logger.debug(f"🔄 Cache hit for {cache_type}: {key}")
    
    def log_cache_miss(self, cache_type: str, key: str):
        """
        Log a cache miss
        
        Args:
            cache_type (str): Type of cache (e.g., "LLM", "Parsing")
            key (str): Cache key
        """
        self.logger.debug(f"🔄 Cache miss for {cache_type}: {key}")


# Global progress and performance loggers
progress_logger = ProgressLogger(__name__)
performance_logger = PerformanceLogger(__name__)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name
    
    Args:
        name (str): Logger name
        
    Returns:
        logging.Logger: Configured logger
    """
    return logging.getLogger(name)


def log_function_call(func):
    """
    Decorator to log function calls with timing
    
    Args:
        func: Function to decorate
        
    Returns:
        Wrapped function
    """
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"📞 Calling function: {func.__name__}")
        
        import time
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            performance_logger.log_execution_time(func.__name__, duration)
            logger.debug(f"✅ Function {func.__name__} completed successfully")
            return result
        except Exception as e:
            duration = time.time() - start_time
            performance_logger.log_execution_time(func.__name__, duration)
            logger.error(f"❌ Function {func.__name__} failed: {str(e)}", exc_info=True)
            raise
    
    return wrapper


def log_class_methods(cls):
    """
    Decorator to log all method calls in a class
    
    Args:
        cls: Class to decorate
        
    Returns:
        Decorated class
    """
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name)
        if callable(attr) and not attr_name.startswith('_'):
            setattr(cls, attr_name, log_function_call(attr))
    return cls