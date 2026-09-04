"""
Error Level Analysis (ELA) Module
===================================
Performs visual forensics by re-compressing images at a controlled quality
rate and measuring compression error discrepancies across the canvas.

Regions that have been digitally altered will exhibit noticeably different
error levels compared to the rest of the document, because the original
JPEG compression artifacts were destroyed and replaced during editing.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

from forensics.models import BoundingBox, ELARegion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default ELA Parameters
# ---------------------------------------------------------------------------
DEFAULT_QUALITY = 90          # Re-compression quality (0-100)
DEFAULT_SCALE = 15            # Error amplification scale factor
DEFAULT_THRESHOLD = 40        # Binary threshold for error map (0-255)
DEFAULT_MIN_AREA = 150        # Minimum contour area to suppress scan noise
DEFAULT_DILATION_KERNEL = 5   # Morphological dilation kernel size
DEFAULT_DILATION_ITERS = 2    # Number of dilation iterations


def compute_ela_map(
    image_path: str | Path,
    quality: int = DEFAULT_QUALITY,
    scale: int = DEFAULT_SCALE,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute the Error Level Analysis difference map.

    Process:
        1. Load the original image.
        2. Re-compress it as JPEG at the specified quality level.
        3. Compute the absolute pixel-wise difference (cv2.absdiff).
        4. Amplify the difference by the scale factor for visibility.

    Args:
        image_path: Path to the source document image.
        quality: JPEG re-compression quality (0-100). Lower values
                 produce larger error differentials. Default is 90%.
        scale: Multiplier applied to the difference map to amplify
               subtle error discrepancies. Default is 15.

    Returns:
        A tuple of (original_image, ela_map) where both are BGR numpy arrays.
        The ELA map is amplified and clipped to [0, 255].
    """
    image_path = Path(image_path)

    # Load original with OpenCV (BGR)
    original = cv2.imread(str(image_path))
    if original is None:
        raise ValueError(f"Could not load image: {image_path}")

    # Re-compress via Pillow to match JPEG encoding behavior accurately
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as tmp:
        tmp_path = tmp.name
        pil_img = Image.open(str(image_path)).convert("RGB")
        pil_img.save(tmp_path, "JPEG", quality=quality)

        # Load the re-compressed version
        recompressed = cv2.imread(tmp_path)

    if recompressed is None:
        raise RuntimeError("Failed to load re-compressed image from temp file")

    # Ensure matching dimensions (handle edge cases with odd pixel counts)
    if original.shape != recompressed.shape:
        recompressed = cv2.resize(recompressed, (original.shape[1], original.shape[0]))

    # Compute absolute difference
    diff = cv2.absdiff(original, recompressed)

    # Amplify and clip
    ela_map = np.clip(diff.astype(np.float32) * scale, 0, 255).astype(np.uint8)

    logger.debug(
        "ELA map computed: shape=%s, mean_error=%.2f, max_error=%d",
        ela_map.shape,
        np.mean(ela_map),
        np.max(ela_map),
    )

    return original, ela_map


def detect_ela_regions(
    ela_map: np.ndarray,
    threshold: int = DEFAULT_THRESHOLD,
    min_area: int = DEFAULT_MIN_AREA,
    dilation_kernel: int = DEFAULT_DILATION_KERNEL,
    dilation_iters: int = DEFAULT_DILATION_ITERS,
) -> List[ELARegion]:
    """Detect anomalous regions from an ELA difference map.

    Computer Vision Pipeline:
        1. Convert ELA map to grayscale.
        2. Apply binary thresholding to isolate high-error pixels.
        3. Apply morphological dilation to merge nearby anomalous pixels
           into cohesive regions.
        4. Find external contours of the dilated binary mask.
        5. Filter contours by minimum area to suppress scan noise.
        6. Generate bounding boxes and compute per-region error statistics.

    Args:
        ela_map: The amplified ELA difference map (BGR, uint8).
        threshold: Binary threshold cutoff. Pixels with error above
                   this value are flagged as anomalous.
        min_area: Minimum contour area in pixels. Contours smaller
                  than this are treated as ambient scan noise and discarded.
        dilation_kernel: Size of the square structuring element for
                         morphological dilation.
        dilation_iters: Number of dilation iterations to merge nearby regions.

    Returns:
        A list of ELARegion objects, each containing the bounding box,
        mean error intensity, and area of the detected region.
    """
    # Convert to grayscale for thresholding
    gray = cv2.cvtColor(ela_map, cv2.COLOR_BGR2GRAY)

    # Binary threshold
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # Morphological dilation to merge nearby anomalous pixels
    kernel = np.ones((dilation_kernel, dilation_kernel), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=dilation_iters)

    # Find external contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions: List[ELARegion] = []

    for contour in contours:
        area = cv2.contourArea(contour)

        # Noise suppression: skip small contours
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        # Compute mean error intensity within the bounding box
        roi = gray[y : y + h, x : x + w]
        mean_error = float(np.mean(roi))

        region = ELARegion(
            bounding_box=BoundingBox(x=x, y=y, w=w, h=h),
            mean_error=round(mean_error, 2),
            area=int(area),
        )
        regions.append(region)

    # Sort by area descending (largest tampered regions first)
    regions.sort(key=lambda r: r.area, reverse=True)

    logger.debug(
        "ELA detection found %d regions (filtered from %d contours, min_area=%d)",
        len(regions),
        len(contours),
        min_area,
    )

    return regions


def save_ela_visualization(
    original: np.ndarray,
    ela_map: np.ndarray,
    regions: List[ELARegion],
    output_path: str | Path,
) -> Path:
    """Save a side-by-side visualization of original vs. ELA with bounding boxes.

    Args:
        original: The original document image (BGR).
        ela_map: The amplified ELA difference map (BGR).
        regions: Detected ELA regions with bounding boxes.
        output_path: Where to save the visualization image.

    Returns:
        The path to the saved visualization.
    """
    output_path = Path(output_path)

    # Draw bounding boxes on a copy of the original
    annotated = original.copy()
    for region in regions:
        bb = region.bounding_box
        color = (0, 0, 255)  # Red in BGR
        cv2.rectangle(annotated, (bb.x, bb.y), (bb.x + bb.w, bb.y + bb.h), color, 2)
        label = f"err:{region.mean_error:.0f} area:{region.area}"
        cv2.putText(
            annotated,
            label,
            (bb.x, bb.y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1,
        )

    # Create side-by-side canvas
    h, w = original.shape[:2]
    canvas = np.zeros((h, w * 2 + 10, 3), dtype=np.uint8)
    canvas[:, :w] = annotated
    canvas[:, w + 10 :] = ela_map

    cv2.imwrite(str(output_path), canvas)
    logger.info("ELA visualization saved to %s", output_path)

    return output_path
