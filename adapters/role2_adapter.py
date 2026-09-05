"""
Role 2 Adapter: Cross-Document Validation & Consistency Rules
=============================================================
Translates the canonical document bundle into the dictionary structure
expected by Role 2 rules_engine.py, executes single and cross-document checks,
and transforms output flags into the canonical flag contract.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from modules.role2_rules.rules_engine import run_rules as role2_run_rules
from schemas import CanonicalFlag
from utils.doc_mapping import map_to_role2_doc_type

logger = logging.getLogger("role2_adapter")


def evaluate_application_rules(
    application_id: str,
    applicant_name: str,
    documents: List[Dict[str, Any]],
) -> List[CanonicalFlag]:
    """Execute Role 2 cross-document verification rules on the complete bundle.

    Args:
        application_id: Unique application identifier.
        applicant_name: Name of the primary applicant.
        documents: List of document dicts containing:
            - "document_id": str
            - "doc_type": str (canonical)
            - "flat_fields": Dict[str, str] (extracted OCR fields)
            - "tampering_detected": bool (from Role 3)

    Returns:
        List of CanonicalFlag items produced by single-doc and cross-doc rules.
    """
    flags: List[CanonicalFlag] = []

    # Format document payload for Role 2
    r2_documents = []
    doc_id_map = {}  # doc_type -> document_id for traceability

    for doc in documents:
        canonical_type = doc.get("doc_type", "supporting_document")
        r2_type = map_to_role2_doc_type(canonical_type)
        flat_f = doc.get("flat_fields", {})
        tampering = bool(doc.get("tampering_detected", False))

        r2_documents.append({
            "doc_type": r2_type,
            "fields": flat_f,
            "tampering_detected": tampering,
        })
        doc_id_map[r2_type] = doc.get("document_id")

    # If applicant_name is specified and not present as an application_form, create virtual application_form
    # so check_income_consistency and check_fuzzy_field have a baseline to compare against
    has_app_form = any(d["doc_type"] == "application_form" for d in r2_documents)
    if not has_app_form and applicant_name and applicant_name != "Unknown":
        r2_documents.append({
            "doc_type": "application_form",
            "fields": {
                "name": applicant_name,
            },
            "tampering_detected": False,
        })

    app_payload = {
        "application_id": application_id,
        "applicant_name": applicant_name,
        "documents": r2_documents,
    }

    try:
        logger.info(
            f"Calling real Role 2 Rules Engine on {application_id} with {len(r2_documents)} documents"
        )
        raw_flags = role2_run_rules(app_payload)

        for idx, rf in enumerate(raw_flags, start=1):
            severity = str(rf.get("severity", "MEDIUM")).upper()
            if severity not in ("HIGH", "MEDIUM", "LOW"):
                severity = "MEDIUM"

            category = str(rf.get("category", "CROSS_DOC_MISMATCH"))
            msg = str(rf.get("message", "Rule mismatch detected."))
            confidence = float(rf.get("confidence", 1.0))
            evidence = rf.get("evidence", {})

            # Attempt to resolve which document this flag belongs to
            target_doc_id = None
            target_doc_type = None
            if evidence:
                target_doc_type = evidence.get("document_1") or evidence.get("doc_type")
                if target_doc_type:
                    target_doc_id = doc_id_map.get(target_doc_type)

            explanation = None
            if evidence:
                explanation = "Evidence: " + ", ".join(f"{k}='{v}'" for k, v in evidence.items())

            flags.append(
                CanonicalFlag(
                    flag_id=f"FLAG-R2-{idx:03d}",
                    severity=severity,
                    category=category,
                    message=msg,
                    confidence=round(confidence, 2),
                    document_id=target_doc_id,
                    document_type=target_doc_type,
                    source="ROLE_2",
                    rule=category,
                    explanation=explanation,
                )
            )

        logger.info(f"Role 2 Rules Engine produced {len(flags)} flags for {application_id}")
        return flags

    except Exception as e:
        logger.exception(f"Unexpected error in Role 2 rules execution for {application_id}: {e}")
        flags.append(
            CanonicalFlag(
                flag_id=f"FLAG-R2-ERR-001",
                severity="MEDIUM",
                category="SYSTEM_ERROR",
                message=f"Cross-document validation rules could not be completed: {str(e)}",
                confidence=1.0,
                source="ROLE_2",
                explanation="Rules engine encountered an internal exception.",
            )
        )
        return flags
