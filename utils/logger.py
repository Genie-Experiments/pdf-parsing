"""
Centralized logging configuration for PDF Parsing Pipeline.

This module provides a unified logging system with consistent formatting,
appropriate log levels, and configurable outputs for the entire pipeline.
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Log levels mapping for easy access
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# Custom formatter for consistent output
class PipelineFormatter(logging.Formatter):
    """Custom formatter with color support and consistent structure."""

    # Color codes for different log levels
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def __init__(self, use_color: bool = True):
        self.use_color = use_color
        super().__init__()

    def format(self, record):
        """Format log record with consistent structure."""
        # Create base format
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        module_name = record.name.split(".")[-1]  # Get just the module name

        # Apply colors if enabled
        if self.use_color and hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
            level_color = self.COLORS.get(record.levelname, "")
            reset_color = self.COLORS["RESET"]
            level_name = f"{level_color}{record.levelname:<8}{reset_color}"
        else:
            level_name = f"{record.levelname:<8}"

        # Format the message
        base_msg = f"[{timestamp}] {level_name} [{module_name}] {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            base_msg += f"\n{self.formatException(record.exc_info)}"

        return base_msg


class PipelineLogger:
    """Main logging manager for the PDF parsing pipeline."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.setup_logging()
            self._initialized = True

    def setup_logging(
        self,
        level: str = "INFO",
        log_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ) -> None:
        """
        Setup centralized logging configuration.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional log file path. If None, only console logging is used
            max_file_size: Maximum log file size before rotation
            backup_count: Number of backup files to keep
        """
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))

        # Clear any existing handlers
        root_logger.handlers.clear()

        # Console handler with color formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = PipelineFormatter(use_color=True)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        root_logger.addHandler(console_handler)

        # File handler if log file is specified
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_path, maxBytes=max_file_size, backupCount=backup_count
            )
            file_formatter = PipelineFormatter(use_color=False)
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)  # File logs everything
            root_logger.addHandler(file_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger for a specific module."""
        return logging.getLogger(name)


# Global logger instance
_logger_manager = PipelineLogger()


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Setup logging for the entire application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
    """
    _logger_manager.setup_logging(level=level, log_file=log_file)


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name, typically __name__

    Returns:
        Logger instance
    """
    if name is None:
        # Get caller's module name
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_module = frame.f_back.f_globals.get("__name__", "unknown")
            name = caller_module
        else:
            name = "pdf-parsing"

    return _logger_manager.get_logger(name)


# Convenience functions for common logging patterns
def log_step(step_number: int, description: str, logger: logging.Logger = None) -> None:
    """Log a pipeline step with consistent formatting."""
    if logger is None:
        logger = get_logger("pipeline")

    separator = "=" * 60
    logger.info("")
    logger.info(separator)
    logger.info("STEP %d: %s", step_number, description)
    logger.info(separator)


def log_file_processing(file_path: str, logger: logging.Logger = None) -> None:
    """Log file processing with consistent formatting."""
    if logger is None:
        logger = get_logger("file-processor")

    relative_path = (
        str(Path(file_path).relative_to(Path.cwd()))
        if Path(file_path).is_absolute()
        else file_path
    )
    logger.info("Processing: %s", relative_path)


def log_success(message: str, logger: logging.Logger = None) -> None:
    """Log a success message."""
    if logger is None:
        logger = get_logger()
    logger.info("✓ %s", message)


def log_error(message: str, logger: logging.Logger = None) -> None:
    """Log an error message."""
    if logger is None:
        logger = get_logger()
    logger.error("✗ %s", message)


def log_warning(message: str, logger: logging.Logger = None) -> None:
    """Log a warning message."""
    if logger is None:
        logger = get_logger()
    logger.warning("⚠ %s", message)


def log_processing_stats(
    total: int, processed: int, failed: int, logger: logging.Logger = None
) -> None:
    """Log processing statistics."""
    if logger is None:
        logger = get_logger("stats")

    success_rate = (processed / total * 100) if total > 0 else 0
    logger.info(
        "Processing completed - Total: %d, Processed: %d, Failed: %d (%.1f%% success)",
        total,
        processed,
        failed,
        success_rate,
    )
