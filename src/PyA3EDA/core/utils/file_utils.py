"""
File Utilities Module

Provides basic file I/O operations and a helper function to sanitize strings for use in filenames.
"""

import logging
from pathlib import Path

# import re
from PyA3EDA.core.constants import Constants


def read_text(file_path: Path) -> str:
    """
    Reads and returns the text of the given file.
    """
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore").rstrip()
    except Exception as e:
        logging.error(f"Error reading file '{file_path}': {e}")
        return ""


def write_text(file_path: Path, content: str) -> bool:
    """
    Writes content to a file and returns True if successful.
    """
    try:
        file_path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        logging.error(f"Error writing file '{file_path}': {e}")
        return False


def sanitize_filename(name: str) -> str:
    """
    Sanitizes a string to be safe for use as a filename.
    Replaces characters based on the Constants.ESCAPE_MAP.
    """
    for old, new in Constants.ESCAPE_MAP.items():
        name = name.replace(old, new)
    # Optionally, remove any remaining non-alphanumeric characters.
    # name = re.sub(r'[^A-Za-z0-9\-_]+', '_', name)
    return name.strip("_")
