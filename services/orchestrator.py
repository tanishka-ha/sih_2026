"""
Main Pipeline Orchestration Service
===================================
Coordinates the entire document verification pipeline:
Storage -> Normalization -> Role 1 (OCR) -> Role 3 (Forensics) -> Role 2 (Cross-Doc Rules)
-> Result Merger -> SQLite Persistence -> SHA-256 Audit Trail -> Master JSON.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session

from adapters.role1_adapter import extract_page_fields
from adapters.role2_adapter import evaluate_application_rules
from adapters.role3_adapter import analyze_page_tampering
from audit.audit_log import AuditLogger
from db.models import (
    ApplicationModel,
    DocumentModel,
    ExtractedFieldModel,
    FlagModel,
    VerificationRunModel,
)
from schemas import (
    CanonicalFlag,
    DocumentBundleResult,
    MasterBundleResponse,
    PageResult,
    TamperingInfo,
)
from services.file_normalizer import FileNormalizerService
from services.result_merger import merge_and_rank_results
from utils.doc_mapping import normalize_doc_type

logger = logging.getLogger("orchestrator")


class VerificationOrchestrator:
    def __init__(
        self,
        normalizer_service: Optional[FileNormalizerService] = None,
    ):
        self.normalizer = normalizer_service or FileNormalizerService()

    @staticmethod
    def generate_application_id(custom_id: Optional[str] = None) -> str:
        """Generate a clean application ID or sanitize the user-provided ID."""
        if custom_id and custom_id.strip():
            clean = "".join(c for c in custom_id.strip() if c.isalnum() or c in ("-", "_"))
            if clean:
                return clean
        token = uuid.uuid4().hex[:5].upper()
        return f"APP-2026-{token}"

    async def verify_bundle(
        self,
        files: List[UploadFile],
        application_id: Optional[str] = None,
        applicant_name: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> MasterBundleResponse:
        """Execute the end-to-end scholarship document verification pipeline."""
        app_id = self.generate_application_id(application_id)
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        start_time = datetime.now(timezone.utc).isoformat()

        logger.info(f"=== STARTING VERIFICATION BUNDLE: {app_id} ({len(files)} files) ===")

        audit_logger = AuditLogger(db) if db else None
        if audit_logger:
            audit_logger.log_event(
                app_id,
                "APPLICATION_CREATED",
                {"application_id": app_id, "files_count": len(files)},
            )

        # Clean up prior documents/flags for this application_id if re-submitted
        if db:
            db.query(FlagModel).filter(FlagModel.application_id == app_id).delete()
            db.query(DocumentModel).filter(DocumentModel.application_id == app_id).delete()
            db.commit()

            run_record = VerificationRunModel(
                run_id=run_id,
                application_id=app_id,
                started_at=start_time,
                completed_at=start_time,
                status="RUNNING",
            )
            db.add(run_record)
            db.commit()

        # Step 1: Save & Normalize All Uploaded Files
        normalized_records = []
        has_partial_failures = False
        all_flags: List[CanonicalFlag] = []

        for f in files:
            norm_res = await self.normalizer.save_and_normalize(app_id, f)
            normalized_records.append(norm_res)
            if not norm_res["success"]:
                has_partial_failures = True
                all_flags.append(
                    CanonicalFlag(
                        flag_id="FLAG-NORM-ERR",
                        severity="HIGH",
                        category="FORMAT_ERROR",
                        message=f"File '{norm_res['original_filename']}' could not be normalized: {norm_res.get('error', {}).get('message', 'Invalid file')}",
                        confidence=1.0,
                        document_id=norm_res["document_id"],
                        source="ROLE_4",
                        explanation="Input normaliser rejected this document.",
                    )
                )

        if audit_logger:
            audit_logger.log_event(
                app_id,
                "FILES_UPLOADED",
                {"file_names": [r["original_filename"] for r in normalized_records]},
            )
            audit_logger.log_event(
                app_id,
                "FILES_NORMALIZED",
                {"successful_docs": sum(1 for r in normalized_records if r["success"])},
            )

        # Step 2: Run Role 1 (OCR) and Role 3 (Forensics) per document
        bundle_documents: List[DocumentBundleResult] = []
        role2_docs_payload = []
        extracted_applicant_name = applicant_name

        for norm_doc in normalized_records:
            doc_id = norm_doc["document_id"]
            orig_name = norm_doc["original_filename"]
            doc_type = normalize_doc_type(orig_name)

            if not norm_doc["success"]:
                # Record failed document in bundle without pages
                bundle_documents.append(
                    DocumentBundleResult(
                        document_id=doc_id,
                        doc_type=doc_type,
                        original_filename=orig_name,
                        pages=[],
                    )
                )
                continue

            page_paths = norm_doc["page_image_paths"]
            doc_pages: List[PageResult] = []
            flat_fields_for_doc: Dict[str, str] = {}
            doc_tampering_detected = False

            # Persist document metadata in SQLite
            if db:
                db_doc = DocumentModel(
                    document_id=doc_id,
                    application_id=app_id,
                    document_type=doc_type,
                    original_filename=orig_name,
                    original_path=norm_doc["original_path"],
                    page_count=len(page_paths),
                )
                db.add(db_doc)
                db.commit()

            for page_idx, page_path in enumerate(page_paths, start=1):
                # 2A: Role 1 OCR
                schema_fields, raw_info, ocr_flags = extract_page_fields(
                    page_image_path=page_path,
                    doc_type=doc_type,
                    original_filename=orig_name,
                    page_num=page_idx,
                )
                all_flags.extend(ocr_flags)

                for k, v in schema_fields.items():
                    if k not in flat_fields_for_doc and v.value:
                        flat_fields_for_doc[k] = v.value
                    if not extracted_applicant_name and k == "name" and v.value:
                        extracted_applicant_name = v.value

                # Persist extracted fields in SQLite
                if db:
                    for f_name, f_data in raw_info.items():
                        db_field = ExtractedFieldModel(
                            document_id=doc_id,
                            page_number=page_idx,
                            field_name=f_name,
                            raw_value=f_data.get("raw_value"),
                            normalized_value=f_data.get("normalized_value"),
                            confidence=f_data.get("confidence", 1.0),
                            bounding_box=json.dumps(f_data.get("bounding_box", [])),
                        )
                        db.add(db_field)
                    db.commit()

                # 2B: Role 3 Forensics
                tampering_info, forensic_flags = analyze_page_tampering(
                    page_image_path=page_path,
                    page_num=page_idx,
                    doc_id=doc_id,
                    doc_type=doc_type,
                )
                all_flags.extend(forensic_flags)
                if tampering_info.detected:
                    doc_tampering_detected = True

                doc_pages.append(
                    PageResult(
                        page_number=page_idx,
                        fields=schema_fields,
                        tampering=tampering_info,
                    )
                )

            bundle_documents.append(
                DocumentBundleResult(
                    document_id=doc_id,
                    doc_type=doc_type,
                    original_filename=orig_name,
                    pages=doc_pages,
                )
            )

            role2_docs_payload.append({
                "document_id": doc_id,
                "doc_type": doc_type,
                "flat_fields": flat_fields_for_doc,
                "tampering_detected": doc_tampering_detected,
            })

        if audit_logger:
            audit_logger.log_event(app_id, "OCR_COMPLETED", {"documents_processed": len(bundle_documents)})
            audit_logger.log_event(app_id, "FORENSICS_COMPLETED", {"documents_analyzed": len(bundle_documents)})

        # Step 3: Run Role 2 Cross-Document Consistency Rules
        final_applicant_name = applicant_name or extracted_applicant_name or "Unknown Applicant"
        rule2_flags = evaluate_application_rules(
            application_id=app_id,
            applicant_name=final_applicant_name,
            documents=role2_docs_payload,
        )
        all_flags.extend(rule2_flags)

        if audit_logger:
            audit_logger.log_event(app_id, "RULES_COMPLETED", {"flags_raised": len(rule2_flags)})

        # Step 4: Merge, Rank, and Generate Summary
        master_response = merge_and_rank_results(
            application_id=app_id,
            applicant_name=final_applicant_name,
            documents=bundle_documents,
            all_flags=all_flags,
            has_partial_failures=has_partial_failures,
        )

        # Step 5: Persist Master Result & Flags in SQLite
        if db:
            # 5A: Application Record
            app_record = db.query(ApplicationModel).filter(ApplicationModel.application_id == app_id).first()
            if not app_record:
                app_record = ApplicationModel(
                    application_id=app_id,
                    created_at=start_time,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    status=master_response.status,
                    applicant_name=final_applicant_name,
                )
                db.add(app_record)
            else:
                app_record.status = master_response.status
                app_record.updated_at = datetime.now(timezone.utc).isoformat()
                app_record.applicant_name = final_applicant_name

            # 5B: Flags
            for flg in master_response.flags:
                flag_record = FlagModel(
                    flag_id=flg.flag_id,
                    application_id=app_id,
                    document_id=flg.document_id,
                    severity=flg.severity,
                    category=flg.category,
                    message=flg.message,
                    confidence=flg.confidence,
                    page=flg.page,
                    bounding_box=json.dumps(flg.bounding_box) if flg.bounding_box else None,
                    source=flg.source,
                    explanation=flg.explanation,
                )
                db.add(flag_record)

            # 5C: Update Verification Run Record
            if run_record:
                run_record.completed_at = datetime.now(timezone.utc).isoformat()
                run_record.status = master_response.status

            db.commit()

        # Step 6: Log Final Cryptographic Verification Event
        if audit_logger:
            audit_logger.log_event(
                app_id,
                "VERIFICATION_COMPLETED",
                {
                    "final_status": master_response.status,
                    "total_flags": master_response.summary.total,
                    "high_flags": master_response.summary.high,
                },
            )

        logger.info(
            f"=== COMPLETED VERIFICATION BUNDLE: {app_id} | Status: {master_response.status} | Flags: {master_response.summary.total} ==="
        )

        return master_response
