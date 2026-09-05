"""
Pydantic Schemas & Data Contracts
=================================
Defines strict, standardized data models for all stages of the verification pipeline:
file conversion, OCR, forensics, cross-checking rules, and the final Master JSON response.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PipelineStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class StageStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class FlagSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# =====================================================================
# CONTEXT MODELS FOR ADAPTER INPUTS
# =====================================================================

class DocumentContext(BaseModel):
    """Encapsulates document metadata and converted image paths passed to adapters."""
    application_id: str
    document_id: str
    original_filename: str
    original_type: str
    image_paths: List[str]


# =====================================================================
# STAGE RESULTS
# =====================================================================

class ConversionResult(BaseModel):
    """Conversion output from file_converter.py."""
    success: bool
    status: StageStatus = StageStatus.SUCCESS
    page_count: int = 0
    image_paths: List[str] = Field(default_factory=list)
    output_directory: Optional[str] = None
    error: Optional[Dict[str, Any]] = None


class OcrResult(BaseModel):
    """Result from Role 1 (OCR and field extraction)."""
    status: StageStatus
    doc_type: Optional[str] = None
    fields: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    error: Optional[str] = None


class ForensicsResult(BaseModel):
    """Result from Role 3 (document forensics / tampering analysis)."""
    status: StageStatus
    tampering_detected: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bounding_boxes: List[Dict[str, Any]] = Field(default_factory=list)
    metadata_flags: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class RuleFlag(BaseModel):
    """A specific anomaly or mismatch flag raised by Role 2 rules engine."""
    severity: FlagSeverity
    category: str
    message: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RulesResult(BaseModel):
    """Result from Role 2 (cross-checking rules and duplicate checks)."""
    status: StageStatus
    flags: List[RuleFlag] = Field(default_factory=list)
    error: Optional[str] = None


# =====================================================================
# MASTER AGGREGATED RESPONSE
# =====================================================================

class DocumentResult(BaseModel):
    """Maintains end-to-end traceability for an individual uploaded document."""
    document_id: str
    original_filename: str
    original_type: Optional[str] = None
    conversion: ConversionResult
    ocr: OcrResult
    forensics: ForensicsResult


class MasterResponse(BaseModel):
    """Unified master response returned to Role 5 Dashboard and downstream clients."""
    application_id: str
    status: PipelineStatus
    documents: List[DocumentResult] = Field(default_factory=list)
    flags: List[RuleFlag] = Field(default_factory=list)
    pipeline_errors: List[str] = Field(default_factory=list)
    created_at: str
