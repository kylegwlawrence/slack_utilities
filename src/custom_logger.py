"""
Logging configuration for the OCR pipeline.

Provides a unified logger setup function for both simple and advanced use cases.
Handles file and console output with configurable formatting and log levels.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str,
    log_dir: str = "logs",
    debug: bool = False,
    console_output: bool = True,
    console_level: Optional[int] = None,
    log_file: Optional[str] = None,
    use_timestamp: bool = True
) -> logging.Logger:
    """
    Set up a unified logger with both file and console handlers.

    Supports both simple and advanced logging use cases. Automatically clears
    existing handlers to prevent duplication. Supports timestamped filenames
    for production and static filenames for development.

    Args:
        name: Logger name
        log_dir: Directory to save log files, defaults to "logs"
        debug: Enable debug mode (verbose logging), defaults to False
        console_output: Whether to print to console, defaults to True
        console_level: Log level for console handler. Defaults to DEBUG in debug mode,
                      WARNING otherwise. Can be overridden (e.g., logging.INFO)
        log_file: Custom log filename. If None, uses '{name}.log' (or timestamped variant).
                 Can be absolute path or relative to log_dir
        use_timestamp: If True and log_file is None, creates timestamped filename like
                      'logger_name_20250122_143025.log'. Defaults to True for production safety

    Returns:
        Configured logger instance with cleared handlers

    Raises:
        IOError: If log directory cannot be created

    Examples:
        >>> # Simple development logger
        >>> logger = setup_logger('myapp', debug=True)
        >>>
        >>> # Production logger with timestamped files
        >>> logger = setup_logger('myapp', log_dir='logs', use_timestamp=True)
        >>>
        >>> # Custom static filename
        >>> logger = setup_logger('myapp', log_file='app.log', use_timestamp=False)
    """
    try:
        # Create log directory if it doesn't exist
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise IOError(f"Failed to create log directory {log_dir}: {e}")

    # Create or get logger and clear existing handlers (prevents duplication)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if debug else logging.WARNING)
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Determine log file path
    if log_file is None:
        if use_timestamp:
            # Production-safe: create unique timestamped files
            log_file = f'{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        else:
            # Development: use static filename
            log_file = f'{name}.log'

    # Make log_file path absolute if not already
    if not os.path.isabs(log_file):
        log_file = os.path.join(log_dir, log_file)

    # File handler
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG if debug else logging.WARNING)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except IOError as e:
        raise IOError(f"Failed to create file handler for {log_file}: {e}")

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        if console_level is not None:
            console_handler.setLevel(console_level)
        else:
            console_handler.setLevel(logging.DEBUG if debug else logging.WARNING)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_custom_logger(name=__name__, level=logging.DEBUG, log_file="app.log"):
    """
    Convenience function for simple logger setup without directory management.

    Wrapper around setup_logger() for quick logging setup. Automatically determines
    the log directory and filename from the log_file parameter.

    Args:
        name: Logger name, defaults to the module name
        level: Logging level (e.g., logging.DEBUG, logging.INFO), defaults to DEBUG
        log_file: Path to log file for file handler output, defaults to "app.log".
                 Can be absolute path or relative path

    Returns:
        Configured Logger instance with console and file handlers

    Examples:
        >>> logger = get_custom_logger(name=__name__, level=logging.DEBUG)
        >>> logger.info("Starting application")
    """
    # Convert logging level to debug boolean
    debug = level == logging.DEBUG

    # Determine log directory and filename from log_file path
    if os.path.isabs(log_file):
        # If absolute path, extract directory and filename
        log_dir = os.path.dirname(log_file)
        filename = os.path.basename(log_file)
    else:
        # If relative path, use current directory
        log_dir = os.path.dirname(log_file) if os.path.dirname(log_file) else "."
        filename = os.path.basename(log_file)

    # Call setup_logger with parameters for simple use case
    return setup_logger(
        name=name,
        log_dir=log_dir if log_dir else ".",
        debug=debug,
        console_output=True,
        console_level=level,
        log_file=filename,
        use_timestamp=False  # Use static filename for backwards compatibility
    )