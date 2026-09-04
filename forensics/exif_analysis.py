"""
EXIF / Digital Header Forensics Module
========================================
Uses piexif to extract and inspect EXIF metadata embedded in image files.
Flags known image-editing software signatures (Photoshop, Canva, GIMP, etc.)
that indicate the document may have been digitally manipulated.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import piexif
from PIL import Image

from forensics.models import EXIFFlag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known suspicious software signatures (case-insensitive substrings)
# ---------------------------------------------------------------------------
SUSPICIOUS_SOFTWARE: List[Tuple[str, str]] = [
    ("photoshop", "Adobe Photoshop — professional image editor commonly used for document alteration"),
    ("canva", "Canva — cloud-based design tool capable of modifying document content"),
    ("gimp", "GIMP — open-source image editor with advanced manipulation capabilities"),
    ("affinity", "Affinity Photo/Designer — professional-grade image editor"),
    ("paint.net", "Paint.NET — raster image editor with layer support"),
    ("pixlr", "Pixlr — browser-based image editor"),
    ("lightroom", "Adobe Lightroom — photo editing suite"),
    ("capture one", "Capture One — professional image editor"),
    ("snapseed", "Snapseed — mobile photo editor with advanced features"),
    ("fotor", "Fotor — photo editing tool with AI enhancement"),
    ("befunky", "BeFunky — online photo editor"),
    ("illustrator", "Adobe Illustrator — vector editor capable of document modification"),
    ("inkscape", "Inkscape — open-source vector graphics editor"),
    ("corel", "CorelDRAW — graphics editor suite"),
    ("sketch", "Sketch — design tool with image editing capabilities"),
    ("figma", "Figma — collaborative design tool"),
]

# EXIF tags to inspect for software signatures
# Reference: piexif tag IDs
EXIF_SOFTWARE_TAGS = [
    ("0th", piexif.ImageIFD.Software, "Software"),
    ("0th", piexif.ImageIFD.ProcessingSoftware, "ProcessingSoftware"),
    ("Exif", piexif.ExifIFD.UserComment, "UserComment"),
]


def _decode_exif_value(raw_value) -> Optional[str]:
    """Safely decode an EXIF value to a UTF-8 string."""
    if raw_value is None:
        return None
    if isinstance(raw_value, bytes):
        try:
            return raw_value.decode("utf-8", errors="replace").strip("\x00 ")
        except Exception:
            return None
    if isinstance(raw_value, str):
        return raw_value.strip()
    return str(raw_value)


def analyze_exif(image_path: str | Path) -> List[EXIFFlag]:
    """Analyze EXIF metadata for suspicious editing software signatures.

    Args:
        image_path: Path to the image file to analyze.

    Returns:
        A list of EXIFFlag objects for each suspicious tag found.
        Returns an empty list if no suspicious metadata is detected
        or if the image contains no EXIF data.
    """
    image_path = Path(image_path)
    flags: List[EXIFFlag] = []

    if not image_path.exists():
        logger.warning("Image file not found: %s", image_path)
        return flags

    # ------------------------------------------------------------------
    # Attempt piexif extraction (JPEG/TIFF with EXIF segments)
    # ------------------------------------------------------------------
    try:
        exif_dict = piexif.load(str(image_path))
    except piexif.InvalidImageDataError:
        logger.debug("No valid EXIF segment in %s (may be PNG or unsupported format)", image_path.name)
        exif_dict = None
    except Exception as exc:
        logger.debug("piexif load failed for %s: %s", image_path.name, exc)
        exif_dict = None

    if exif_dict:
        for ifd_key, tag_id, tag_name in EXIF_SOFTWARE_TAGS:
            ifd = exif_dict.get(ifd_key, {})
            raw = ifd.get(tag_id)
            value = _decode_exif_value(raw)
            if value:
                _check_software_signature(value, tag_name, flags)

    # ------------------------------------------------------------------
    # Fallback: Pillow metadata extraction (covers PNG tEXt chunks, etc.)
    # ------------------------------------------------------------------
    try:
        with Image.open(str(image_path)) as img:
            info = img.info or {}
            for key in ("Software", "software", "Author", "Comment", "Description"):
                value = info.get(key)
                if value and isinstance(value, (str, bytes)):
                    decoded = _decode_exif_value(value)
                    if decoded:
                        _check_software_signature(decoded, f"PIL:{key}", flags)
    except Exception as exc:
        logger.debug("Pillow metadata extraction failed for %s: %s", image_path.name, exc)

    if flags:
        logger.info("EXIF analysis flagged %d suspicious entries in %s", len(flags), image_path.name)
    else:
        logger.debug("No suspicious EXIF metadata found in %s", image_path.name)

    return flags


def _check_software_signature(value: str, tag_name: str, flags: List[EXIFFlag]) -> None:
    """Check a decoded EXIF value against the known suspicious software list."""
    value_lower = value.lower()
    for keyword, reason in SUSPICIOUS_SOFTWARE:
        if keyword in value_lower:
            flag = EXIFFlag(
                tag=tag_name,
                value=value,
                reason=reason,
            )
            # Avoid duplicate flags for the same tag+keyword pair
            if not any(f.tag == flag.tag and f.value == flag.value for f in flags):
                flags.append(flag)
                logger.debug("Flagged EXIF tag '%s' = '%s' → %s", tag_name, value, reason)
