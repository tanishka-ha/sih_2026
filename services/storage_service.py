"""
Storage Service
===============
Manages safe file storage, application directory structures, and prevents path traversal attacks.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile

from config import STORAGE_DIR, APP_ID_PREFIX

logger = logging.getLogger("storage_service")


class StorageService:
    def __init__(self, base_storage_dir: Optional[Path] = None):
        self.base_dir = (base_storage_dir or STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def generate_application_id(self, custom_id: Optional[str] = None) -> str:
        """Return sanitized client application ID or generate a new unique ID."""
        if custom_id and custom_id.strip():
            # Sanitize custom ID to allow only safe alphanumeric characters, dashes, and underscores
            sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", custom_id.strip())
            if sanitized:
                return sanitized
        # Generate safe random application ID
        unique_token = uuid.uuid4().hex[:8].upper()
        return f"{APP_ID_PREFIX}-{unique_token}"

    def get_application_dirs(self, application_id: str) -> Tuple[Path, Path]:
        """Get or create uploads and converted directories for an application."""
        app_root = self.base_dir / application_id
        uploads_dir = app_root / "uploads"
        converted_dir = app_root / "converted"

        uploads_dir.mkdir(parents=True, exist_ok=True)
        converted_dir.mkdir(parents=True, exist_ok=True)

        return uploads_dir, converted_dir

    async def save_uploaded_file(
        self,
        application_id: str,
        upload_file: UploadFile,
    ) -> Tuple[str, Path, str]:
        """Safely stream and store an UploadFile to disk.

        Args:
            application_id: The active application ID.
            upload_file: FastAPI UploadFile instance.

        Returns:
            Tuple of (document_id, saved_path, original_filename).
        """
        # Step 1: Defensive extraction & sanitization of original filename
        raw_name = upload_file.filename or "uploaded_document"
        original_filename = Path(raw_name).name  # Strips directory traversal (e.g. ../../)
        
        # Strip all unsafe chars except alphanumerics, dots, hyphens, and underscores
        safe_base_name = re.sub(r"[^a-zA-Z0-9._-]", "_", original_filename)
        if not safe_base_name or safe_base_name.startswith("."):
            safe_base_name = f"doc_{safe_base_name}"

        # Step 2: Generate unique document ID and safe storage filename
        doc_uuid = uuid.uuid4().hex[:8]
        document_id = f"DOC-{doc_uuid.upper()}"
        safe_filename = f"{doc_uuid}_{safe_base_name}"

        uploads_dir, _ = self.get_application_dirs(application_id)
        destination_path = uploads_dir / safe_filename

        # Step 3: Stream write to disk in 64KB chunks to conserve memory
        logger.info(f"Saving upload '{original_filename}' as '{safe_filename}' for {application_id}")
        
        try:
            with open(destination_path, "wb") as buffer:
                while content := await upload_file.read(64 * 1024):
                    buffer.write(content)
        finally:
            await upload_file.seek(0)  # Reset pointer for any subsequent reads

        return document_id, destination_path, original_filename
