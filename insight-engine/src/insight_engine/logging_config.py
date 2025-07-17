"""
Structured logging configuration for the Insight Engine application.

This module provides comprehensive logging setup with structured output,
correlation ID support, and environment-specific configuration.
"""

import json
import logging
import logging.config
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from insight_engine.utils.error_utils import get_correlation_id, get_user_id, get_request_id


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    
    Includes correlation ID, user context, and additional metadata
    for better log analysis and monitoring.
    """
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log structure
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add correlation context
        correlation_id = get_correlation_id()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id
        
        user_id = get_user_id()
        if user_id:
            log_entry["user_id"] = user_id
        
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add extra fields from the log record
        if self.include_extra and hasattr(record, '__dict__'):
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'getMessage', 'exc_info',
                    'exc_text', 'stack_info'
                }:
                    try:
                        # Ensure the value is JSON serializable
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Console formatter with colors for different log levels.
    
    Provides human-readable output for development environments.
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and correlation context."""
        # Add color to level name
        level_color = self.COLORS.get(record.levelname, '')
        reset_color = self.COLORS['RESET']
        
        # Build the log message
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        correlation_id = get_correlation_id()
        user_id = get_user_id()
        
        # Base format
        parts = [
            f"{timestamp}",
            f"{level_color}{record.levelname:8}{reset_color}",
            f"{record.name}",
            f"{record.getMessage()}"
        ]
        
        # Add context if available
        context_parts = []
        if correlation_id:
            context_parts.append(f"corr_id={correlation_id[:8]}")
        if user_id:
            context_parts.append(f"user={user_id}")
        
        if context_parts:
            parts.append(f"[{', '.join(context_parts)}]")
        
        # Add location info for errors
        if record.levelno >= logging.ERROR:
            parts.append(f"({record.filename}:{record.lineno})")
        
        log_line = " | ".join(parts)
        
        # Add exception info if present
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)
        
        return log_line


def setup_logging(
    environment: str = "development",
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_json_logs: bool = None,
    enable_console_logs: bool = True
) -> None:
    """
    Set up structured logging for the application.
    
    Args:
        environment: Environment name (development, staging, production)
        log_level: Minimum log level to capture
        log_file: Optional file path for log output
        enable_json_logs: Whether to use JSON formatting (auto-detected if None)
        enable_console_logs: Whether to log to console
    """
    # Auto-detect JSON logging based on environment
    if enable_json_logs is None:
        enable_json_logs = environment in ("staging", "production")
    
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    handlers = []
    
    # Console handler
    if enable_console_logs:
        console_handler = logging.StreamHandler(sys.stdout)
        if enable_json_logs:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(ColoredConsoleFormatter())
        console_handler.setLevel(numeric_level)
        handlers.append(console_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        force=True
    )
    
    # Set specific logger levels
    logger_configs = {
        "uvicorn": logging.WARNING,
        "uvicorn.access": logging.WARNING,
        "fastapi": logging.INFO,
        "httpx": logging.WARNING,
        "google": logging.WARNING,
        "urllib3": logging.WARNING,
        "insight_engine": numeric_level,
    }
    
    for logger_name, level in logger_configs.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "environment": environment,
            "log_level": log_level,
            "json_logs": enable_json_logs,
            "console_logs": enable_console_logs,
            "log_file": log_file,
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class to add logging capabilities to other classes.
    
    Provides a logger instance and convenience methods for structured logging.
    """
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance for this class."""
        return logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def log_info(self, message: str, **kwargs) -> None:
        """Log info message with context."""
        self.logger.info(message, extra=kwargs)
    
    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning message with context."""
        self.logger.warning(message, extra=kwargs)
    
    def log_error(self, message: str, exception: Exception = None, **kwargs) -> None:
        """Log error message with context and optional exception."""
        if exception:
            kwargs["exception_type"] = type(exception).__name__
            kwargs["exception_message"] = str(exception)
        
        self.logger.error(message, extra=kwargs, exc_info=exception is not None)
    
    def log_debug(self, message: str, **kwargs) -> None:
        """Log debug message with context."""
        self.logger.debug(message, extra=kwargs)


def configure_logging_from_config(config: Dict[str, Any]) -> None:
    """
    Configure logging from a configuration dictionary.
    
    Args:
        config: Configuration dictionary with logging settings
    """
    logging_config = config.get("logging", {})
    
    setup_logging(
        environment=config.get("environment", "development"),
        log_level=logging_config.get("level", "INFO"),
        log_file=logging_config.get("file"),
        enable_json_logs=logging_config.get("json_format"),
        enable_console_logs=logging_config.get("console", True)
    )


# Performance logging utilities
class PerformanceLogger:
    """
    Utility class for performance logging and monitoring.
    
    Tracks operation timing and resource usage.
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_operation_time(
        self,
        operation: str,
        duration: float,
        success: bool = True,
        **context
    ) -> None:
        """
        Log operation timing information.
        
        Args:
            operation: Name of the operation
            duration: Duration in seconds
            success: Whether the operation was successful
            **context: Additional context information
        """
        self.logger.info(
            f"Operation completed: {operation}",
            extra={
                "operation": operation,
                "duration_seconds": round(duration, 4),
                "success": success,
                "performance_metric": True,
                **context
            }
        )
    
    def log_resource_usage(
        self,
        operation: str,
        memory_mb: Optional[float] = None,
        cpu_percent: Optional[float] = None,
        **context
    ) -> None:
        """
        Log resource usage information.
        
        Args:
            operation: Name of the operation
            memory_mb: Memory usage in MB
            cpu_percent: CPU usage percentage
            **context: Additional context information
        """
        resource_info = {"operation": operation, "resource_metric": True}
        
        if memory_mb is not None:
            resource_info["memory_mb"] = round(memory_mb, 2)
        
        if cpu_percent is not None:
            resource_info["cpu_percent"] = round(cpu_percent, 2)
        
        resource_info.update(context)
        
        self.logger.info(
            f"Resource usage for {operation}",
            extra=resource_info
        )