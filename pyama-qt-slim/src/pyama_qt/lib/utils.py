"""Utility functions for PyAMA Qt."""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def ensure_dir(path: Path) -> None:
    """Ensure a directory exists, creating it if necessary."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.error(f"Permission denied creating directory: {path}")
    except OSError as e:
        logger.error(f"Error creating directory {path}: {e}")


def find_files_by_extension(directory: Path, extension: str) -> List[Path]:
    """Find all files with a given extension in a directory."""
    if not directory.exists():
        return []

    extension = extension.lstrip(".")
    pattern = f"**/*.{extension}"

    files = []
    for file_path in directory.rglob(pattern):
        if file_path.is_file():
            files.append(file_path)

    return files


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def validate_csv_file(file_path: Path) -> bool:
    """Validate that a file is a CSV file and is readable."""
    if not file_path.exists():
        logger.error(f"File does not exist: {file_path}")
        return False

    if file_path.suffix.lower() != ".csv":
        logger.error(f"File is not a CSV file: {file_path}")
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Try to read the first line to ensure it's readable
            f.readline()
        return True
    except (IOError, UnicodeDecodeError) as e:
        logger.error(f"Error reading CSV file {file_path}: {e}")
        return False


def safe_filename(filename: str) -> str:
    """Create a safe filename by removing/replacing problematic characters."""
    import re

    # Replace problematic characters with underscores
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove multiple consecutive underscores
    safe_name = re.sub(r"_+", "_", safe_name)

    # Remove leading/trailing underscores and whitespace
    safe_name = safe_name.strip("_ \t\n\r")

    # Ensure it's not empty
    if not safe_name:
        safe_name = "untitled"

    return safe_name
