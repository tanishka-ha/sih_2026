"""
Font & Baseline Consistency Analysis Module
=============================================
Detects text manipulations by checking whether character contours along horizontal
text lines deviate from expected baseline alignment, height metrics, or stroke metrics.

Digitally edited text (e.g., altered numbers, inserted digits, modified dates)
frequently exhibits slight vertical offsets (misaligned baselines) or height/width
discrepancies compared to neighboring printed characters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np

from forensics.models import BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class BaselineAnomaly:
    """Represents a text line region with inconsistent font baseline or height metrics."""
    bounding_box: BoundingBox
    baseline_dev: float
    height_dev: float
    description: str


def analyze_font_baseline_consistency(
    image_path: str,
    line_threshold_y: int = 15,
    min_char_width: int = 4,
    min_char_height: int = 8,
    max_char_height: int = 120,
) -> List[BaselineAnomaly]:
    """Analyze text baseline alignment and font height consistency across horizontal lines.

    Args:
        image_path: Path to the input document image.
        line_threshold_y: Y-distance tolerance to group text contours into the same horizontal line.
        min_char_width: Minimum width of character contour to consider.
        min_char_height: Minimum height of character contour to consider.
        max_char_height: Maximum height of character contour to consider.

    Returns:
        List of BaselineAnomaly objects for regions exhibiting baseline/font discrepancies.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        logger.warning(f"Could not load image for font analysis: {image_path}")
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Adaptive threshold to isolate printed text characters
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 8
    )

    # Find character-level contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes: List[Tuple[int, int, int, int]] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if min_char_width <= w <= 150 and min_char_height <= h <= max_char_height:
            boxes.append((x, y, w, h))

    if not boxes:
        return []

    # Sort character boxes by Y-coordinate
    boxes.sort(key=lambda b: b[1])

    # Group boxes into horizontal text lines
    lines: List[List[Tuple[int, int, int, int]]] = []
    current_line: List[Tuple[int, int, int, int]] = [boxes[0]]

    for box in boxes[1:]:
        prev_y = current_line[-1][1]
        if abs(box[1] - prev_y) <= line_threshold_y:
            current_line.append(box)
        else:
            if len(current_line) >= 4:  # Only analyze lines with at least 4 characters
                lines.append(current_line)
            current_line = [box]

    if len(current_line) >= 4:
        lines.append(current_line)

    anomalies: List[BaselineAnomaly] = []

    for line in lines:
        # Sort line boxes horizontally by X
        line.sort(key=lambda b: b[0])

        baselines = np.array([y + h for (x, y, w, h) in line])
        heights = np.array([h for (x, y, w, h) in line])

        median_baseline = np.median(baselines)
        median_height = np.median(heights)

        for (x, y, w, h) in line:
            baseline_diff = abs((y + h) - median_baseline)
            height_diff = abs(h - median_height)

            # Flag characters that deviate significantly (> 3.5px baseline jump or > 50% height diff)
            if baseline_diff > 4.5 or (height_diff > 0.45 * median_height and height_diff > 6):
                anomalies.append(
                    BaselineAnomaly(
                        bounding_box=BoundingBox(x, y, w, h),
                        baseline_dev=round(float(baseline_diff), 2),
                        height_dev=round(float(height_diff), 2),
                        description=f"Font/Baseline offset: baseline_dev={baseline_diff:.1f}px, height_dev={height_diff:.1f}px",
                    )
                )

    return anomalies
