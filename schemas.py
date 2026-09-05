"""
Canonical Pydantic Schemas
==========================
Defines the final Master JSON response contract consumed by the Role 5 Clerk Dashboard.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_FLAGS = "COMPLETED_WITH_FLAGS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class FlagSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FieldValue(BaseModel):
    value: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class TamperingInfo(BaseModel):
    detected: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bounding_boxes: List[List[int]] = Field(default_factory=list)


class PageResult(BaseModel):
    page_number: int
    fields: Dict[str, FieldValue] = Field(default_factory=dict)
    tampering: TamperingInfo = Field(default_factory=TamperingInfo)


class DocumentBundleResult(BaseModel):
    document_id: str
    doc_type: str
    original_filename: str
    pages: List[PageResult] = Field(default_factory=list)


class CanonicalFlag(BaseModel):
    flag_id: str
    severity: str
    category: str
    message: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    document_id: Optional[str] = None
    document_type: Optional[str] = None
    page: Optional[int] = None
    bounding_box: Optional[List[int]] = None
    source: str
    rule: Optional[str] = None
    explanation: Optional[str] = None


class FlagSummary(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    total: int = 0


class MasterBundleResponse(BaseModel):
    application_id: str
    status: str
    applicant_name: str
    documents: List[DocumentBundleResult] = Field(default_factory=list)
    flags: List[CanonicalFlag] = Field(default_factory=list)
    summary: FlagSummary = Field(default_factory=FlagSummary)
