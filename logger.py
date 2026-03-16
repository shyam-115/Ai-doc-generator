"""
Centralized logging setup for AI Doc Generator.

Provides a pre-configured logger with console and optional file handlers.
"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "ai_doc_gen", log_level: str = "INFO") -> logging.Logger:
    """
    Create and configure a logger with a rich console handler.

    Args:
        name: Logger name (used as prefix in log output).
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers in re-imports
    if logger.handlers:
        return logger

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Console handler with readable format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger


def get_file_logger(
    name: str, log_file: str | Path, log_level: str = "DEBUG"
) -> logging.Logger:
    """
    Add a file handler to the named logger.

    Args:
        name: Logger name.
        log_file: Path to the log file.
        log_level: Logging level string.

    Returns:
        Logger with file handler attached.
    """
    logger = setup_logger(name, log_level)
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    return logger


# Default application logger
logger = setup_logger("ai_doc_gen")
