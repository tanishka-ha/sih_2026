"""
Document Normalisation & File Converter Module
==============================================
Role 4: Backend Orchestrator and Input Normalisation Pipeline.

This module validates, safely handles, and normalises user-uploaded scholarship documents
(PDF, JPG, JPEG, PNG) into standard, uniform RGB PNG page images for downstream OCR and
forensics modules.

It does NOT perform OCR, document verification, tampering detection, or any business logic.
Its sole responsibility is strict file validation, resource safety, and standardisation.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # Fallback for older versions
from PIL import Image, ImageOps, UnidentifiedImageError

# =====================================================================
# CONFIGURATION & CONSTANTS
# =====================================================================

MAX_FILE_SIZE_MB: float = 25.0
MAX_PDF_PAGES: int = 50
PDF_RENDER_SCALE: float = 2.0  # Scale 2.0 renders at ~144 DPI (standard 72 DPI * 2.0)
DEFAULT_OUTPUT_BASE_DIR: str = "converted_files"

ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".jpg", ".jpeg", ".png"}
PDF_EXTENSIONS: Set[str] = {".pdf"}
IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png"}

# Magic byte signatures for content validation
PDF_MAGIC_BYTES: bytes = b"%PDF-"
PNG_MAGIC_BYTES: bytes = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC_BYTES: bytes = b"\xff\xd8\xff"

# Setup module logger
logger = logging.getLogger("file_converter")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# =====================================================================
# CUSTOM EXCEPTION HIERARCHY
# =====================================================================

class FileConverterError(Exception):
    """Base exception for all file conversion and normalisation errors."""
    pass


class FileValidationError(FileConverterError):
    """Raised when an uploaded file fails general integrity or security checks."""
    pass


class FileNotFoundErrorCustom(FileValidationError):
    """Raised when the input file path does not exist."""
    pass


class UnsupportedFileTypeError(FileValidationError):
    """Raised when the uploaded file extension or content type is not supported."""
    pass


class FileTooLargeError(FileValidationError):
    """Raised when the input file exceeds the configured size limit."""
    pass


class InvalidPDFError(FileConverterError):
    """Raised when a PDF file is corrupted, malformed, or cannot be opened."""
    pass


class EmptyPDFError(InvalidPDFError):
    """Raised when a PDF file contains zero pages or is zero bytes."""
    pass


class PasswordProtectedPDFError(InvalidPDFError):
    """Raised when a PDF is encrypted and requires a password."""
    pass


class TooManyPagesError(InvalidPDFError):
    """Raised when a PDF exceeds the maximum allowed page count."""
    pass


class InvalidImageError(FileConverterError):
    """Raised when an image is corrupted, truncated, or unreadable."""
    pass


class OutputDirectoryError(FileConverterError):
    """Raised when the output directory cannot be created or accessed due to permissions."""
    pass


class UnexpectedConversionError(FileConverterError):
    """Raised when an unhandled error occurs during the conversion process."""
    pass


# =====================================================================
# RESPONSE BUILDERS (CONTRACT DEFINITION)
# =====================================================================

def build_success_response(
    original_filename: str,
    original_type: str,
    image_paths: List[str],
    output_directory: str,
) -> Dict[str, Any]:
    """Construct a uniform structured success response dictionary.

    Args:
        original_filename: Name of the original uploaded file.
        original_type: Normalized file type ("pdf", "jpg", "jpeg", "png").
        image_paths: List of string paths to the converted PNG images.
        output_directory: String path to the directory containing converted files.

    Returns:
        Dict matching the success contract specification.
    """
    return {
        "success": True,
        "original_filename": original_filename,
        "original_type": original_type,
        "page_count": len(image_paths),
        "image_paths": image_paths,
        "output_directory": output_directory,
        "error": None,
    }


def build_error_response(
    original_filename: str,
    original_type: Optional[str],
    error_type: str,
    error_message: str,
) -> Dict[str, Any]:
    """Construct a uniform structured failure response dictionary.

    Args:
        original_filename: Name of the original uploaded file (or empty string).
        original_type: Normalized file type if identified, else None or empty.
        error_type: Name or category of the error (e.g., "InvalidPDFError").
        error_message: Clean, descriptive message explaining the failure.

    Returns:
        Dict matching the error contract specification.
    """
    return {
        "success": False,
        "original_filename": original_filename,
        "original_type": original_type,
        "page_count": 0,
        "image_paths": [],
        "output_directory": None,
        "error": {
            "type": error_type,
            "message": error_message,
        },
    }


# =====================================================================
# VALIDATION FUNCTIONS
# =====================================================================

def validate_input_file(file_path: Union[str, Path]) -> Path:
    """Validate that the input path exists, is a regular file, and is readable.

    Args:
        file_path: Path to the uploaded document.

    Returns:
        Resolved absolute Path object.

    Raises:
        FileNotFoundCustomError: If the file does not exist.
        FileValidationError: If the path is a directory or not a regular file.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        logger.warning(f"File not found at path: {file_path}")
        raise FileNotFoundErrorCustom(f"The input file '{file_path}' does not exist.")

    if not path.is_file():
        logger.warning(f"Path is not a regular file: {path}")
        raise FileValidationError(f"The path '{path}' is not a regular file.")

    return path


def validate_file_size(file_path: Path, max_size_mb: float = MAX_FILE_SIZE_MB) -> None:
    """Check that the file size is greater than 0 and within configured limits.

    Args:
        file_path: Path to the validated file.
        max_size_mb: Maximum allowed file size in megabytes.

    Raises:
        FileValidationError: If the file is 0 bytes.
        FileTooLargeError: If file exceeds max_size_mb.
    """
    file_size_bytes = file_path.stat().st_size
    if file_size_bytes == 0:
        logger.warning(f"File is empty (0 bytes): {file_path}")
        raise FileValidationError(f"The file '{file_path.name}' is empty (0 bytes).")

    max_size_bytes = int(max_size_mb * 1024 * 1024)
    if file_size_bytes > max_size_bytes:
        file_size_actual_mb = file_size_bytes / (1024 * 1024)
        logger.warning(
            f"File too large: {file_path.name} is {file_size_actual_mb:.2f} MB "
            f"(limit: {max_size_mb} MB)"
        )
        raise FileTooLargeError(
            f"File size ({file_size_actual_mb:.2f} MB) exceeds maximum allowed limit of {max_size_mb} MB."
        )


def detect_file_type(file_path: Path) -> str:
    """Detect and validate file type by extension and content magic bytes.

    Args:
        file_path: Path to the validated file.

    Returns:
        Normalized file type string without leading dot (e.g. 'pdf', 'jpg', 'jpeg', 'png').

    Raises:
        UnsupportedFileTypeError: If extension or content format is not supported.
        InvalidPDFError: If file has .pdf extension but lacks PDF signature.
        InvalidImageError: If file has image extension but lacks image signature.
    """
    extension = file_path.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        logger.warning(f"Rejected unsupported file extension '{extension}': {file_path.name}")
        raise UnsupportedFileTypeError(
            f"Unsupported file format '{extension}'. Allowed formats: PDF, JPG, JPEG, PNG."
        )

    # Perform magic bytes inspection to prevent file extension spoofing
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
    except Exception as e:
        logger.error(f"Failed to read file header for {file_path}: {e}")
        raise FileValidationError(f"Unable to read file headers: {e}")

    if extension in PDF_EXTENSIONS:
        if not header.startswith(PDF_MAGIC_BYTES):
            logger.warning(f"File '{file_path.name}' has .pdf extension but lacks PDF magic bytes header.")
            raise InvalidPDFError(
                f"File '{file_path.name}' has a .pdf extension but contains invalid header signatures."
            )
        return "pdf"

    if extension in {".jpg", ".jpeg"}:
        if not header.startswith(JPEG_MAGIC_BYTES):
            logger.warning(f"File '{file_path.name}' has JPEG extension but lacks JPEG magic bytes.")
            raise InvalidImageError(
                f"File '{file_path.name}' has a JPEG extension but is not a valid JPEG image."
            )
        return extension.lstrip(".")

    if extension == ".png":
        if not header.startswith(PNG_MAGIC_BYTES):
            logger.warning(f"File '{file_path.name}' has PNG extension but lacks PNG magic bytes.")
            raise InvalidImageError(
                f"File '{file_path.name}' has a PNG extension but is not a valid PNG image."
            )
        return "png"

    raise UnsupportedFileTypeError(f"Unsupported file type for extension: {extension}")


def validate_image(image_path: Path) -> None:
    """Open and fully verify image structure and pixel decodability.

    Pillow's verify() reads headers. Calling img.load() actually decodes pixel data,
    which catches truncated or corrupted images.

    Args:
        image_path: Path to image file.

    Raises:
        InvalidImageError: If the image cannot be decoded or is corrupted.
    """
    try:
        with Image.open(image_path) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as e:
        logger.warning(f"Image header verification failed for {image_path.name}: {e}")
        raise InvalidImageError(f"Corrupted or invalid image header: {e}") from e

    # Re-open and decode pixel stream to catch truncated or corrupted payload
    try:
        with Image.open(image_path) as img:
            img.load()
    except (OSError, ValueError, SyntaxError) as e:
        logger.warning(f"Image pixel decoding failed for {image_path.name}: {e}")
        raise InvalidImageError(f"Image data is corrupted or truncated: {e}") from e


# =====================================================================
# OUTPUT DIRECTORY MANAGEMENT
# =====================================================================

def prepare_output_directory(
    base_output_dir: Optional[Union[str, Path]] = None,
    job_prefix: Optional[str] = None,
) -> Path:
    """Create a clean, isolated output directory for the conversion job.

    To prevent concurrent race conditions, collision, or accidental overwrites,
    a unique subfolder is generated for each job.

    Args:
        base_output_dir: Base directory for output. Defaults to DEFAULT_OUTPUT_BASE_DIR.
        job_prefix: Optional prefix for the job directory name (e.g. original file stem).

    Returns:
        Path object pointing to the newly created isolated output directory.

    Raises:
        OutputDirectoryError: If creation fails due to permissions or OS errors.
    """
    try:
        base_path = Path(base_output_dir or DEFAULT_OUTPUT_BASE_DIR).resolve()
        base_path.mkdir(parents=True, exist_ok=True)

        unique_id = uuid.uuid4().hex[:8]
        folder_name = f"{job_prefix}_{unique_id}" if job_prefix else unique_id
        target_dir = base_path / folder_name
        target_dir.mkdir(parents=True, exist_ok=False)

        logger.debug(f"Prepared isolated output directory: {target_dir}")
        return target_dir
    except (PermissionError, OSError) as e:
        logger.error(f"Failed to create output directory: {e}")
        raise OutputDirectoryError(
            f"Failed to initialize output directory: {e}"
        ) from e


def _cleanup_directory(directory: Path) -> None:
    """Safely remove a directory and its contents during error rollback."""
    try:
        if directory.exists() and directory.is_dir():
            shutil.rmtree(directory)
            logger.debug(f"Cleaned up directory on failure: {directory}")
    except Exception as e:
        logger.warning(f"Failed to clean up directory {directory} during rollback: {e}")


# =====================================================================
# PDF CONVERSION
# =====================================================================

def convert_pdf_to_images(
    pdf_path: Path,
    target_dir: Path,
    render_scale: float = PDF_RENDER_SCALE,
    max_pages: int = MAX_PDF_PAGES,
) -> List[Path]:
    """Convert each page of a PDF document into a standard PNG image.

    Args:
        pdf_path: Path to the validated PDF file.
        target_dir: Target directory where PNG pages will be saved.
        render_scale: Scale factor for rendering (2.0 = ~144 DPI).
        max_pages: Maximum permitted number of pages.

    Returns:
        List of Path objects for all successfully generated page images in order.

    Raises:
        InvalidPDFError: If PDF cannot be opened or is corrupted.
        PasswordProtectedPDFError: If PDF is encrypted/password protected.
        EmptyPDFError: If PDF contains zero pages.
        TooManyPagesError: If PDF page count exceeds max_pages.
        UnexpectedConversionError: If rendering fails on any page.
    """
    logger.info(f"Starting PDF conversion for: {pdf_path.name}")
    doc: Optional[fitz.Document] = None
    created_paths: List[Path] = []

    try:
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            logger.warning(f"PyMuPDF failed to open PDF '{pdf_path.name}': {e}")
            raise InvalidPDFError(
                f"The uploaded PDF could not be opened or may be corrupted: {e}"
            ) from e

        # Check for password protection / encryption
        if doc.is_encrypted or doc.needs_pass:
            logger.warning(f"PDF is encrypted / password protected: {pdf_path.name}")
            raise PasswordProtectedPDFError(
                f"The PDF '{pdf_path.name}' is password-protected or encrypted."
            )

        page_count = len(doc)
        if page_count == 0:
            logger.warning(f"PDF contains 0 pages: {pdf_path.name}")
            raise EmptyPDFError(f"The PDF '{pdf_path.name}' contains zero pages.")

        if page_count > max_pages:
            logger.warning(
                f"PDF exceeds page limit: {page_count} pages (limit: {max_pages})"
            )
            raise TooManyPagesError(
                f"The PDF has {page_count} pages, which exceeds the maximum limit of {max_pages} pages."
            )

        # Render matrix for high-quality OCR (scale 2.0 = 144 DPI)
        matrix = fitz.Matrix(render_scale, render_scale)

        for page_idx in range(page_count):
            try:
                page = doc.load_page(page_idx)
                # alpha=False renders onto white background, avoiding transparent black patches
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                page_filename = f"page_{page_idx + 1:03d}.png"
                output_file = target_dir / page_filename
                pix.save(str(output_file))
                created_paths.append(output_file)
                logger.debug(
                    f"Rendered page {page_idx + 1}/{page_count} to {output_file.name}"
                )
            except Exception as e:
                logger.error(f"Failed rendering page {page_idx + 1} of '{pdf_path.name}': {e}")
                raise UnexpectedConversionError(
                    f"Failed to render page {page_idx + 1} of PDF '{pdf_path.name}': {e}"
                ) from e

        logger.info(
            f"Successfully converted PDF '{pdf_path.name}' ({len(created_paths)} pages)"
        )
        return created_paths

    except Exception:
        # Safe rollback: remove any partial page files created before error
        for p in created_paths:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        raise
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


# =====================================================================
# IMAGE CONVERSION & NORMALISATION
# =====================================================================

def _normalize_image_mode_to_rgb(img: Image.Image) -> Image.Image:
    """Normalize arbitrary image color modes (RGBA, LA, P, CMYK, L) to standard 3-channel RGB.

    Safely composites transparency onto a pure white background so that OCR and forensics
    modules never encounter black silhouettes or corrupted backgrounds.

    Args:
        img: Input Pillow Image.

    Returns:
        Standardized RGB Pillow Image.
    """
    # Auto-orient based on EXIF tags (e.g. mobile photo orientation)
    try:
        img = ImageOps.exif_transpose(img) or img
    except Exception:
        pass

    mode = img.mode

    if mode == "RGB":
        return img.copy()

    if mode == "RGBA":
        # Create solid white canvas and paste using alpha channel as mask
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background

    if mode == "LA":
        # Grayscale with Alpha
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background

    if mode == "P":
        # Palette mode - check if transparency is defined
        if "transparency" in img.info:
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[3])
            return background
        return img.convert("RGB")

    if mode in ("CMYK", "L", "1", "YCbCr", "LAB", "HSV"):
        return img.convert("RGB")

    # Fallback for any other exotic modes
    return img.convert("RGB")


def convert_image_to_png(image_path: Path, target_dir: Path) -> List[Path]:
    """Convert an uploaded JPG, JPEG, or PNG into a standardized single-page RGB PNG.

    Args:
        image_path: Path to the validated source image.
        target_dir: Target directory where standard PNG will be saved.

    Returns:
        List containing a single Path object pointing to 'page_001.png'.

    Raises:
        InvalidImageError: If the image cannot be read or processed.
        UnexpectedConversionError: If saving fails.
    """
    logger.info(f"Starting image normalisation for: {image_path.name}")
    validate_image(image_path)

    output_path = target_dir / "page_001.png"

    try:
        with Image.open(image_path) as raw_img:
            normalized_img = _normalize_image_mode_to_rgb(raw_img)

        try:
            normalized_img.save(output_path, format="PNG", optimize=False)
            logger.info(f"Successfully normalised image '{image_path.name}' -> {output_path.name}")
            return [output_path]
        finally:
            normalized_img.close()

    except Exception as e:
        logger.error(f"Failed converting image '{image_path.name}' to standard PNG: {e}")
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception:
                pass
        raise UnexpectedConversionError(
            f"Failed to convert image '{image_path.name}' to standard PNG: {e}"
        ) from e


# =====================================================================
# MAIN PUBLIC ORCHESTRATOR
# =====================================================================

def convert_to_images(
    input_path: Union[str, Path],
    output_directory: Optional[Union[str, Path]] = None,
    render_scale: float = PDF_RENDER_SCALE,
    max_file_size_mb: float = MAX_FILE_SIZE_MB,
    max_pdf_pages: int = MAX_PDF_PAGES,
) -> Dict[str, Any]:
    """Main orchestrator function: normalises an uploaded PDF or image into standard PNGs.

    Downstream modules (OCR and Forensics) receive a uniform list of image paths and
    do not need to know whether the original document was a PDF, JPG, or PNG.

    Args:
        input_path: Path to the uploaded document.
        output_directory: Optional base output directory. If None, uses default.
        render_scale: Zoom scale for PDF page rendering (default: 2.0).
        max_file_size_mb: Configurable size limit in megabytes.
        max_pdf_pages: Configurable maximum page limit for PDFs.

    Returns:
        Structured result dictionary conforming to the pipeline contract:
        - success: bool
        - original_filename: str
        - original_type: str or None
        - page_count: int
        - image_paths: List[str]
        - output_directory: str or None
        - error: None or Dict with 'type' and 'message'
    """
    # Defensive extraction of initial filename for error responses
    raw_path_str = str(input_path) if input_path is not None else "unknown"
    original_filename = Path(raw_path_str).name if input_path else "unknown"
    detected_type: Optional[str] = None
    target_job_dir: Optional[Path] = None

    logger.info(f"Received conversion request for: {raw_path_str}")

    try:
        # Step 1: Validate file existence and file structure
        resolved_path = validate_input_file(input_path)
        original_filename = resolved_path.name

        # Step 2: Validate file size
        validate_file_size(resolved_path, max_size_mb=max_file_size_mb)

        # Step 3: Detect and validate file type & header signature
        detected_type = detect_file_type(resolved_path)
        logger.debug(f"Detected file type: {detected_type} for {original_filename}")

        # Step 4: Prepare isolated output directory for this job
        safe_prefix = "".join(c for c in resolved_path.stem if c.isalnum() or c in ("-", "_"))[:20]
        target_job_dir = prepare_output_directory(
            base_output_dir=output_directory,
            job_prefix=safe_prefix or "doc",
        )

        # Step 5: Execute conversion based on detected type
        if detected_type == "pdf":
            generated_paths = convert_pdf_to_images(
                pdf_path=resolved_path,
                target_dir=target_job_dir,
                render_scale=render_scale,
                max_pages=max_pdf_pages,
            )
        else:
            generated_paths = convert_image_to_png(
                image_path=resolved_path,
                target_dir=target_job_dir,
            )

        # Convert generated Path objects to normalized string paths
        str_image_paths = [str(p) for p in generated_paths]
        str_target_dir = str(target_job_dir)

        logger.info(
            f"Successfully processed '{original_filename}': "
            f"produced {len(str_image_paths)} pages in {str_target_dir}"
        )

        return build_success_response(
            original_filename=original_filename,
            original_type=detected_type,
            image_paths=str_image_paths,
            output_directory=str_target_dir,
        )

    except FileNotFoundErrorCustom as e:
        return build_error_response(original_filename, detected_type, "FileNotFoundError", str(e))

    except UnsupportedFileTypeError as e:
        return build_error_response(original_filename, detected_type, "UnsupportedFileTypeError", str(e))

    except FileTooLargeError as e:
        return build_error_response(original_filename, detected_type, "FileTooLargeError", str(e))

    except FileValidationError as e:
        return build_error_response(original_filename, detected_type, "FileValidationError", str(e))

    except PasswordProtectedPDFError as e:
        if target_job_dir:
            _cleanup_directory(target_job_dir)
        return build_error_response(original_filename, detected_type or "pdf", "PasswordProtectedPDFError", str(e))

    except EmptyPDFError as e:
        if target_job_dir:
            _cleanup_directory(target_job_dir)
        return build_error_response(original_filename, detected_type or "pdf", "EmptyPDFError", str(e))

    except TooManyPagesError as e:
        if target_job_dir:
            _cleanup_directory(target_job_dir)
        return build_error_response(original_filename, detected_type or "pdf", "TooManyPagesError", str(e))

    except InvalidPDFError as e:
        if target_job_dir:
            _cleanup_directory(target_job_dir)
        return build_error_response(original_filename, detected_type or "pdf", "InvalidPDFError", str(e))

    except InvalidImageError as e:
        if target_job_dir:
            _cleanup_directory(target_job_dir)
        return build_error_response(original_filename, detected_type or "image", "InvalidImageError", str(e))

    except OutputDirectoryError as e:
        return build_error_response(original_filename, detected_type, "OutputDirectoryError", str(e))

    except UnexpectedConversionError as e:
        if target_job_dir:
            _cleanup_directory(target_job_dir)
        return build_error_response(original_filename, detected_type, "UnexpectedConversionError", str(e))

    except Exception as e:
        # Catch-all safeguard: prevent any unhandled exception from crashing caller/FastAPI
        logger.exception(f"Unhandled exception during conversion of {original_filename}: {e}")
        if target_job_dir:
            _cleanup_directory(target_job_dir)
        return build_error_response(
            original_filename,
            detected_type,
            "UnexpectedConversionError",
            f"An unexpected internal error occurred: {type(e).__name__}: {e}",
        )


# =====================================================================
# CLI DEMO / EXAMPLE RUNNER
# =====================================================================

if __name__ == "__main__":
    import json
    import sys

    print("=" * 70)
    print("AI Document Verification System - File Normalisation Module")
    print("=" * 70)

    if len(sys.argv) > 1:
        target_path = sys.argv[1]
        out_dir = sys.argv[2] if len(sys.argv) > 2 else None
        print(f"Processing: {target_path}")
        result = convert_to_images(target_path, output_directory=out_dir)
        print("\nStructured Result:")
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python file_converter.py <path_to_document> [optional_output_dir]")
        print("\nRun 'python test_file_converter.py' to execute the comprehensive test suite.")
