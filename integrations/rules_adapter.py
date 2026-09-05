"""
Role 2 Integration: Cross-Document Validation & Rules Adapter
=============================================================
Provides a stable interface for cross-document consistency checks and fraud rules.
Currently implements a realistic MOCK.

TEAM INTEGRATION NOTE:
When Role 2 delivers their validation rules engine, replace the contents
of `_execute_role_2_rules()` with calls to their actual engine.
Do NOT change the signature of `run_rules_engine()`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from models.schemas import DocumentResult, FlagSeverity, RuleFlag, RulesResult, StageStatus

logger = logging.getLogger("rules_adapter")


# =====================================================================
# ROLE 2 MOCK IMPLEMENTATION (REPLACE WHEN ROLE 2 CODE IS DELIVERED)
# =====================================================================

def _execute_role_2_rules(documents: List[DocumentResult]) -> List[RuleFlag]:
    """Internal implementation of cross-document verification rules.

    Cross-checks extracted OCR entities and forensic markers across all bundle documents.
    """
    flags: List[RuleFlag] = []

    # Check 1: Forensics Tampering Propagation
    for doc in documents:
        if doc.forensics.status == StageStatus.SUCCESS and doc.forensics.tampering_detected:
            flags.append(
                RuleFlag(
                    severity=FlagSeverity.CRITICAL,
                    category="TAMPERING_SUSPECTED",
                    message=(
                        f"Forensic anomalies detected in '{doc.original_filename}'. "
                        "Manual inspection required."
                    ),
                    confidence=doc.forensics.confidence,
                )
            )

    # Check 2: Cross-Document Name Consistency
    extracted_names: Dict[str, str] = {}
    for doc in documents:
        if doc.ocr.status == StageStatus.SUCCESS and doc.ocr.fields:
            name = doc.ocr.fields.get("name")
            if name:
                extracted_names[doc.original_filename] = str(name).strip().lower()

    if len(extracted_names) > 1:
        unique_names = set(extracted_names.values())
        if len(unique_names) > 1:
            flags.append(
                RuleFlag(
                    severity=FlagSeverity.MEDIUM,
                    category="CROSS_DOC_MISMATCH",
                    message=(
                        f"Name discrepancy detected across submitted documents: {list(unique_names)}."
                    ),
                    confidence=0.88,
                )
            )

    # Check 3: Income Threshold Validation
    for doc in documents:
        if doc.ocr.status == StageStatus.SUCCESS and doc.ocr.doc_type == "income_certificate":
            income_str = doc.ocr.fields.get("income_amount")
            if income_str:
                try:
                    income_val = float(income_str)
                    if income_val > 250000:  # Example 2.5 LPA threshold
                        flags.append(
                            RuleFlag(
                                severity=FlagSeverity.HIGH,
                                category="INCOME_LIMIT_EXCEEDED",
                                message=(
                                    f"Declared income (INR {income_val}) exceeds eligibility threshold."
                                ),
                                confidence=0.95,
                            )
                        )
                except ValueError:
                    pass

    return flags


# =====================================================================
# PUBLIC STABLE INTERFACE
# =====================================================================

def run_rules_engine(application_id: str, documents: List[DocumentResult]) -> RulesResult:
    """Execute cross-document validation rules across all processed documents.

    Args:
        application_id: Unique application identifier.
        documents: List of DocumentResult instances with completed conversion, OCR, and Forensics.

    Returns:
        RulesResult with evaluation status and any generated RuleFlag items.
    """
    logger.info(f"Running Rules Engine on Application ID: {application_id} ({len(documents)} documents)")

    # Testing hook: allow simulating rules engine failure via application_id convention
    if "rules_fail" in application_id.lower():
        logger.warning(f"Simulating rules engine failure for Application {application_id}")
        return RulesResult(
            status=StageStatus.FAILED,
            flags=[],
            error="Cross-document validation rules service encountered an internal error.",
        )

    try:
        flags = _execute_role_2_rules(documents)
        return RulesResult(
            status=StageStatus.SUCCESS,
            flags=flags,
            error=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in Rules Engine for {application_id}: {e}")
        return RulesResult(
            status=StageStatus.FAILED,
            flags=[],
            error=f"Rules evaluation error: {str(e)}",
        )
