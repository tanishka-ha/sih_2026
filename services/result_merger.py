"""
Result Merger Service
=====================
Merges Role 1 OCR extraction, Role 3 Forensics findings, and Role 2 Rules flags
into a cohesive, ranked Master Response for the Role 5 Clerk Dashboard.
Enforces the strict No-Auto-Rejection policy.
"""

from __future__ import annotations

from typing import List
from schemas import (
    ApplicationStatus,
    CanonicalFlag,
    DocumentBundleResult,
    FlagSummary,
    MasterBundleResponse,
)

SEVERITY_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def merge_and_rank_results(
    application_id: str,
    applicant_name: str,
    documents: List[DocumentBundleResult],
    all_flags: List[CanonicalFlag],
    has_partial_failures: bool = False,
) -> MasterBundleResponse:
    """Combine document models and flags into the final Master JSON response."""
    # Step 1: Sort and rank flags by severity (HIGH -> MEDIUM -> LOW) and confidence
    all_flags.sort(
        key=lambda f: (
            SEVERITY_ORDER.get(f.severity.upper(), 0),
            f.confidence,
        ),
        reverse=True,
    )

    # Step 2: Assign clean sequential flag IDs
    for idx, flag in enumerate(all_flags, start=1):
        flag.flag_id = f"FLAG-{idx:03d}"

    # Step 3: Compute summary counts
    high_count = sum(1 for f in all_flags if f.severity.upper() == "HIGH")
    medium_count = sum(1 for f in all_flags if f.severity.upper() == "MEDIUM")
    low_count = sum(1 for f in all_flags if f.severity.upper() == "LOW")
    total_count = len(all_flags)

    summary = FlagSummary(
        high=high_count,
        medium=medium_count,
        low=low_count,
        total=total_count,
    )

    # Step 4: Determine overall Application Status (NO AUTO-REJECTION)
    if not documents or all(len(d.pages) == 0 for d in documents):
        overall_status = ApplicationStatus.FAILED
    elif has_partial_failures:
        overall_status = ApplicationStatus.PARTIAL
    elif total_count > 0:
        overall_status = ApplicationStatus.COMPLETED_WITH_FLAGS
    else:
        overall_status = ApplicationStatus.COMPLETED

    return MasterBundleResponse(
        application_id=application_id,
        status=overall_status.value,
        applicant_name=applicant_name or "Unknown",
        documents=documents,
        flags=all_flags,
        summary=summary,
    )
