"""
Global Configuration & Settings
===============================
Configures paths, defaults, and environmental parameters for the Role 4 Backend Orchestrator.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Set

# Base directory paths
BASE_DIR: Path = Path(__file__).resolve().parent
STORAGE_DIR: Path = BASE_DIR / "storage"

# Ensure storage directory exists
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Pipeline limits & defaults (consistent with file_converter.py)
MAX_FILE_SIZE_MB: float = 25.0
MAX_PDF_PAGES: int = 50
PDF_RENDER_SCALE: float = 2.0
ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".jpg", ".jpeg", ".png"}

# Application defaults
APP_ID_PREFIX: str = "APP-2026"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
