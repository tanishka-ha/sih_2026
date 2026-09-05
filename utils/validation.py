"""
Security & Input Validation Utilities
=====================================
Sanitizes filenames, prevents path traversal, and validates file boundaries.
"""

import re
from pathlib import Path
from typing import Set

ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE_MB: float = 25.0


def sanitize_filename(raw_filename: str) -> str:
    """Sanitize an uploaded filename to prevent directory traversal and injection."""
    if not raw_filename:
        return "unnamed_document"

    # Strip any leading directories (e.g. ../../etc/passwd or C:\Windows\...)
    clean_name = Path(raw_filename).name

    # Remove all characters except alphanumeric, dot, hyphen, underscore
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", clean_name)

    # Prevent hidden files or relative dots
    while safe.startswith("."):
        safe = safe[1:]

    return safe or "document"


def validate_file_extension(filename: str, allowed: Set[str] = ALLOWED_EXTENSIONS) -> str:
    """Check that file extension is supported (case-insensitive)."""
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise ValueError(
            f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(allowed))}"
        )
    return ext
