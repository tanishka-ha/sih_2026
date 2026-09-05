from adapters.role1_adapter import extract_page_fields, extract_document_fields
from adapters.role2_adapter import evaluate_application_rules
from adapters.role3_adapter import analyze_page_tampering

__all__ = [
    "extract_page_fields",
    "extract_document_fields",
    "evaluate_application_rules",
    "analyze_page_tampering",
]
