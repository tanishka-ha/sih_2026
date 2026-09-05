"""
Role 4: Pipeline Service (Core Orchestrator)
============================================
Coordinates the end-to-end processing pipeline:
1. Receives and persists uploaded files.
2. Calls existing file_converter.py to normalise inputs into standard PNGs.
3. Invokes Role 1 (OCR) and Role 3 (Forensics) concurrently per document.
4. Aggregates results and calls Role 2 (Cross-Document Rules Engine).
5. Assembles and returns the Master JSON Response.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import List, Optional
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from file_converter import convert_to_images
from integrations.forensics_adapter import run_forensics_on_document
from integrations.ocr_adapter import run_ocr_on_document
from integrations.rules_adapter import run_rules_engine
from models.schemas import (
    ConversionResult,
    DocumentContext,
    DocumentResult,
    ForensicsResult,
    MasterResponse,
    OcrResult,
    PipelineStatus,
    RuleFlag,
    StageStatus,
)
from services.storage_service import StorageService

logger = logging.getLogger("pipeline_service")


class PipelineService:
    def __init__(self, storage_service: Optional[StorageService] = None):
        self.storage_service = storage_service or StorageService()

    async def process_document_bundle(
        self,
        files: List[UploadFile],
        application_id: Optional[str] = None,
    ) -> MasterResponse:
        """Process a bundle of uploaded documents through the verification pipeline.

        Args:
            files: List of uploaded files (PDF, JPG, JPEG, PNG).
            application_id: Optional client-provided application ID.

        Returns:
            MasterResponse containing full document traceability, stage outputs, and flags.
        """
        app_id = self.storage_service.generate_application_id(application_id)
        created_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        logger.info(f"--- STARTING PIPELINE BUNDLE: Application ID {app_id} with {len(files)} files ---")

        pipeline_errors: List[str] = []
        documents: List[DocumentResult] = []

        if not files:
            logger.warning(f"Application {app_id} submitted with no files.")
            return MasterResponse(
                application_id=app_id,
                status=PipelineStatus.FAILED,
                documents=[],
                flags=[],
                pipeline_errors=["No files were uploaded in this submission bundle."],
                created_at=created_timestamp,
            )

        _, converted_dir = self.storage_service.get_application_dirs(app_id)

        # Process each uploaded document
        for upload_file in files:
            orig_filename = upload_file.filename or "unknown"
            logger.info(f"Processing upload: {orig_filename} for Application {app_id}")

            try:
                # Step 1: Safely save the upload to disk
                doc_id, saved_path, orig_name = await self.storage_service.save_uploaded_file(
                    application_id=app_id,
                    upload_file=upload_file,
                )

                # Step 2: Normalise file to standard PNG page images using existing file_converter
                # Run in threadpool to keep async event loop responsive
                raw_conv_result = await run_in_threadpool(
                    convert_to_images,
                    input_path=saved_path,
                    output_directory=converted_dir,
                )

                if raw_conv_result["success"]:
                    conv_model = ConversionResult(
                        success=True,
                        status=StageStatus.SUCCESS,
                        page_count=raw_conv_result["page_count"],
                        image_paths=raw_conv_result["image_paths"],
                        output_directory=raw_conv_result["output_directory"],
                        error=None,
                    )

                    # Create context object for downstream adapters
                    doc_context = DocumentContext(
                        application_id=app_id,
                        document_id=doc_id,
                        original_filename=orig_name,
                        original_type=raw_conv_result["original_type"],
                        image_paths=raw_conv_result["image_paths"],
                    )

                    # Step 3: Run OCR (Role 1) and Forensics (Role 3) concurrently
                    ocr_task = run_in_threadpool(run_ocr_on_document, doc_context)
                    forensics_task = run_in_threadpool(run_forensics_on_document, doc_context)

                    ocr_model, forensics_model = await asyncio.gather(ocr_task, forensics_task)

                else:
                    # Conversion failed (e.g. corrupted PDF or invalid image)
                    logger.warning(
                        f"Conversion failed for document {doc_id} ({orig_name}): "
                        f"{raw_conv_result.get('error')}"
                    )
                    conv_model = ConversionResult(
                        success=False,
                        status=StageStatus.FAILED,
                        page_count=0,
                        image_paths=[],
                        output_directory=None,
                        error=raw_conv_result.get("error"),
                    )

                    # Downstream stages are marked SKIPPED rather than failed
                    ocr_model = OcrResult(
                        status=StageStatus.SKIPPED,
                        doc_type=None,
                        fields={},
                        confidence=0.0,
                        error="File conversion failed; OCR stage skipped.",
                    )
                    forensics_model = ForensicsResult(
                        status=StageStatus.SKIPPED,
                        tampering_detected=False,
                        confidence=0.0,
                        bounding_boxes=[],
                        metadata_flags=[],
                        error="File conversion failed; forensics stage skipped.",
                    )

                # Assemble DocumentResult maintaining end-to-end traceability
                doc_result = DocumentResult(
                    document_id=doc_id,
                    original_filename=orig_name,
                    original_type=raw_conv_result.get("original_type"),
                    conversion=conv_model,
                    ocr=ocr_model,
                    forensics=forensics_model,
                )
                documents.append(doc_result)

            except Exception as e:
                # Catch-all safeguard per document: prevent one bad upload from crashing the pipeline
                logger.exception(f"Unexpected error processing document '{orig_filename}': {e}")
                pipeline_errors.append(f"Document '{orig_filename}' failed unexpectedly: {str(e)}")
                documents.append(
                    DocumentResult(
                        document_id="DOC-ERROR",
                        original_filename=orig_filename,
                        original_type=None,
                        conversion=ConversionResult(
                            success=False,
                            status=StageStatus.FAILED,
                            page_count=0,
                            image_paths=[],
                            output_directory=None,
                            error={"type": "InternalError", "message": str(e)},
                        ),
                        ocr=OcrResult(
                            status=StageStatus.SKIPPED,
                            error="Internal processing error occurred prior to OCR.",
                        ),
                        forensics=ForensicsResult(
                            status=StageStatus.SKIPPED,
                            tampering_detected=False,
                            error="Internal processing error occurred prior to forensics.",
                        ),
                    )
                )

        # Step 4: Run Role 2 Cross-Document Validation Rules Engine
        rules_result = await run_in_threadpool(run_rules_engine, app_id, documents)
        flags: List[RuleFlag] = rules_result.flags

        if rules_result.status == StageStatus.FAILED:
            pipeline_errors.append(f"Rules engine encountered an error: {rules_result.error}")

        # Step 5: Compute overall Pipeline Status
        conversion_successes = sum(1 for d in documents if d.conversion.success)
        total_docs = len(documents)

        if conversion_successes == total_docs:
            overall_status = PipelineStatus.SUCCESS
        elif conversion_successes == 0:
            overall_status = PipelineStatus.FAILED
        else:
            overall_status = PipelineStatus.PARTIAL_SUCCESS

        logger.info(
            f"--- COMPLETED PIPELINE BUNDLE: Application {app_id} | "
            f"Status: {overall_status.value} | Converted: {conversion_successes}/{total_docs} | Flags: {len(flags)} ---"
        )

        return MasterResponse(
            application_id=app_id,
            status=overall_status,
            documents=documents,
            flags=flags,
            pipeline_errors=pipeline_errors,
            created_at=created_timestamp,
        )
