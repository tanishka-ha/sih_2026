"""
Data models for forensics analysis results.
All results conform to a standardized JSON-serializable schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional


class SeverityLevel(str, Enum):
    """Severity classification for detected tampering."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BoundingBox:
    """A bounding box around a detected tampered region.

    Attributes:
        x: Top-left x coordinate (pixels).
        y: Top-left y coordinate (pixels).
        w: Width of the box (pixels).
        h: Height of the box (pixels).
    """
    x: int
    y: int
    w: int
    h: int

    def to_list(self) -> List[int]:
        return [self.x, self.y, self.w, self.h]


@dataclass
class EXIFFlag:
    """A suspicious EXIF metadata flag.

    Attributes:
        tag: The EXIF tag name (e.g., 'Software', 'ProcessingSoftware').
        value: The raw value found in the header.
        reason: Human-readable explanation of why this is suspicious.
    """
    tag: str
    value: str
    reason: str


@dataclass
class ELARegion:
    """A region flagged by Error Level Analysis.

    Attributes:
        bounding_box: The bounding box enclosing the anomalous region.
        mean_error: Mean error intensity within the region (0-255).
        area: Area of the region in pixels.
    """
    bounding_box: BoundingBox
    mean_error: float
    area: int


@dataclass
class ForensicsResult:
    """Standardized forensics analysis result.

    This is the primary output schema delivered to Role 4 (Backend Orchestrator)
    and Role 5 (Frontend Dashboard).

    Attributes:
        tampering_detected: Whether any form of tampering was detected.
        bounding_boxes: List of [x, y, w, h] bounding boxes for tampered regions.
        severity: Overall severity level of the detected tampering.
        confidence: Dynamic confidence metric (0.0 - 1.0) based on tamper
                     pixel density relative to overall document area.
        exif_flags: List of suspicious EXIF metadata entries.
        ela_regions: List of regions flagged by Error Level Analysis.
        tamper_pixel_ratio: Ratio of tampered pixels to total document pixels.
        document_dimensions: [width, height] of the analyzed document.
        analysis_details: Additional metadata about the analysis run.
    """
    tampering_detected: bool = False
    bounding_boxes: List[List[int]] = field(default_factory=list)
    severity: SeverityLevel = SeverityLevel.NONE
    confidence: float = 0.0
    exif_flags: List[EXIFFlag] = field(default_factory=list)
    ela_regions: List[ELARegion] = field(default_factory=list)
    font_anomalies: List[dict] = field(default_factory=list)
    tamper_pixel_ratio: float = 0.0
    document_dimensions: List[int] = field(default_factory=lambda: [0, 0])
    analysis_details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        result = asdict(self)
        # Enum -> string
        result["severity"] = self.severity.value
        return result

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
