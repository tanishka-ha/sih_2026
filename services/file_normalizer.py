"""
File Normalization Service
==========================
Manages application directory layouts (originals vs normalized pages)
and wraps the frozen file_converter.py engine.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple
from fastapi import UploadFile

from config import BASE_DIR
from file_converter import convert_to_images
from utils.validation import sanitize_filename

logger = logging.getLogger("file_normalizer")
UPLOADS_BASE_DIR = BASE_DIR / "uploads"


class FileNormalizerService:
    def __init__(self, base_dir: Path = UPLOADS_BASE_DIR):
        self.base_dir = base_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_application_paths(self, application_id: str) -> Tuple[Path, Path]:
        """Get or create application-specific originals and normalized directory paths."""
        app_dir = self.base_dir / application_id
        originals_dir = app_dir / "originals"
        normalized_dir = app_dir / "normalized"

        originals_dir.mkdir(parents=True, exist_ok=True)
        normalized_dir.mkdir(parents=True, exist_ok=True)

        return originals_dir, normalized_dir

    async def save_and_normalize(
        self,
        application_id: str,
        upload_file: UploadFile,
    ) -> Dict[str, Any]:
        """Save an uploaded file and normalize it into standard page PNG images.

        Returns:
            Dict containing:
            - document_id: str
            - original_filename: str
            - original_path: Path
            - success: bool
            - page_count: int
            - page_image_paths: List[str]
            - error: Optional[Dict[str, Any]]
        """
        raw_name = upload_file.filename or "uploaded_file"
        safe_name = sanitize_filename(raw_name)
        doc_uuid = uuid.uuid4().hex[:8].upper()
        document_id = f"DOC-{doc_uuid}"

        originals_dir, normalized_dir = self.get_application_paths(application_id)

        # Save original file with safe unique prefix
        file_stem = Path(safe_name).stem
        file_ext = Path(safe_name).suffix
        safe_original_name = f"{file_stem}_{doc_uuid.lower()}{file_ext}"
        original_saved_path = originals_dir / safe_original_name

        logger.info(f"Saving upload '{raw_name}' -> '{original_saved_path}'")
        try:
            with open(original_saved_path, "wb") as buffer:
                while chunk := await upload_file.read(64 * 1024):
                    buffer.write(chunk)
        finally:
            await upload_file.seek(0)

        # Target subfolder for normalized pages: normalized/<file_stem>_<uuid>/
        doc_normalized_dir = normalized_dir / f"{file_stem}_{doc_uuid.lower()}"
        doc_normalized_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Normalizing '{safe_original_name}' via file_converter.py")
        conv_result = convert_to_images(
            input_path=original_saved_path,
            output_directory=doc_normalized_dir,
        )

        return {
            "document_id": document_id,
            "original_filename": raw_name,
            "original_path": str(original_saved_path),
            "success": conv_result["success"],
            "original_type": conv_result.get("original_type"),
            "page_count": conv_result.get("page_count", 0),
            "page_image_paths": conv_result.get("image_paths", []),
            "error": conv_result.get("error"),
        }
