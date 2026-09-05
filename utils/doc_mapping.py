"""
Centralized Document Type & Field Mapping
=========================================
Normalizes document types and field aliases between Role 1, Role 2, Role 3,
and the canonical Role 4 representations.
"""

from typing import Dict, Optional

# Canonical document type mapping across modules
CANONICAL_DOC_TYPES = {
    "income_certificate": "income_certificate",
    "income": "income_certificate",
    "category_certificate": "category_certificate",
    "caste_certificate": "category_certificate",
    "caste": "category_certificate",
    "category": "category_certificate",
    "marksheet": "marksheet",
    "academic_marksheet": "marksheet",
    "gradesheet": "marksheet",
    "scorecard": "marksheet",
    "id_proof": "id_proof",
    "aadhaar": "id_proof",
    "pan": "id_proof",
    "voter_id": "id_proof",
    "driving_licence": "id_proof",
    "identity": "id_proof",
    "bank_proof": "bank_proof",
    "bank_passbook": "bank_proof",
    "ration_card": "bank_proof",
    "birth_certificate": "id_proof",
    "application_form": "application_form",
    "application": "application_form",
}

# Role 1 expects specific keys from DOC_LABELS
ROLE1_DOC_TYPE_MAPPING = {
    "income_certificate": "income_certificate",
    "category_certificate": "caste_certificate",
    "marksheet": "marksheet",
    "id_proof": "aadhaar",
    "bank_proof": "default",
    "application_form": "default",
}

# Role 2 expects specific doc_types in REQUIRED_FIELDS
ROLE2_DOC_TYPE_MAPPING = {
    "income_certificate": "income_certificate",
    "category_certificate": "category_certificate",
    "caste_certificate": "category_certificate",
    "marksheet": "marksheet",
    "id_proof": "id_proof",
    "bank_proof": "bank_proof",
    "application_form": "application_form",
}

FIELD_ALIAS_MAPPING: Dict[str, str] = {
    "income": "income_amount",
    "annual_income": "income_amount",
    "annual income": "income_amount",
    "caste": "category",
    "date": "issue_date",
    "issue_date": "issue_date",
    "issue date": "issue_date",
    "roll": "roll_number",
    "roll_number": "roll_number",
    "roll number": "roll_number",
    "birth": "dob",
    "date of birth": "dob",
    "aadhaar": "id_number",
    "id": "id_number",
    "id_number": "id_number",
    "id number": "id_number",
    "members": "family_members",
    "certificate": "certificate_id",
    "certificate_id": "certificate_id",
    "certificate id": "certificate_id",
    "candidate_name": "name",
    "applicant_name": "name",
    "account": "account_number",
    "account_number": "account_number",
    "account number": "account_number",
    "account_holder": "name",
    "account holder": "name",
    "father_name": "father",
    "father name": "father",
}


def normalize_doc_type(raw_name: str) -> str:
    """Normalize a raw filename or type string into a canonical document type."""
    if not raw_name:
        return "supporting_document"

    clean = raw_name.lower().replace("-", "_").replace(" ", "_")

    for key, canonical in CANONICAL_DOC_TYPES.items():
        if key in clean:
            return canonical

    return "supporting_document"


def map_to_role1_doc_type(canonical_type: str) -> str:
    """Map canonical document type to Role 1 DOC_LABELS key."""
    return ROLE1_DOC_TYPE_MAPPING.get(canonical_type, "default")


def map_to_role2_doc_type(canonical_type: str) -> str:
    """Map canonical document type to Role 2 REQUIRED_FIELDS key."""
    return ROLE2_DOC_TYPE_MAPPING.get(canonical_type, canonical_type)


def normalize_field_name(raw_field: str) -> str:
    """Map field aliases to standard field names used in verification rules."""
    clean = raw_field.lower().strip()
    return FIELD_ALIAS_MAPPING.get(clean, clean)
