"""
Core utilities for AI Doc Generator.
"""

import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from logger import setup_logger

logger = setup_logger("utils")


def write_atomic(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    """
    Write content to a file atomically.

    Writes to a temporary file first, then renames it to the target path.
    This prevents corrupt or half-written files if the process crashes mid-write.

    Args:
        path: Target file path.
        content: String content to write.
        encoding: Text encoding (default utf-8).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=target.suffix)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(temp_path, target)
    except Exception:
        os.unlink(temp_path)
        raise


def save_json_locked(path: str | Path, data: Any) -> None:
    """
    Save JSON data to a file safely using an exclusive file lock.

    Prevents concurrent writers from corrupting the file. Only works
    reliably on POSIX systems.

    Args:
        path: Target file path.
        data: JSON-serializable data.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(target, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())  # force write to disk before unlocking
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as exc:
        logger.warning("Failed to safely save JSON to %s: %s", target, exc)
        raise
