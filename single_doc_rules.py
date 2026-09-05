from datetime import datetime, date
import re
# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# Define which fields are compulsory for each document type.
REQUIRED_FIELDS = {
    "income_certificate": [
        "name",
        "income_amount",
        "issue_date",
        "certificate_id"
    ],
    "category_certificate": [
        "name",
        "issue_date",
        "certificate_id"
    ],
    "marksheet": [
        "name",
        "dob"
    ],
    "id_proof": [
        "name",
        "dob",
        "id_number"
    ],
    "bank_proof": [
        "name",
        "account_number"
    ]
}
# Validity periods for the prototype.
# None means the document does not expire.
VALIDITY_DAYS = {
    "income_certificate": 365,
    "category_certificate": 365,
    "marksheet": None,
    "id_proof": None,
    "bank_proof": None
}
# Example certificate ID patterns for our synthetic dataset.
CERTIFICATE_PATTERNS = {
    "income_certificate": r"^INC\d{5}$",
    "category_certificate": r"^CAT\d{5}$"
}
# ---------------------------------------------------------
# FLAG CREATOR
# ---------------------------------------------------------
def create_flag(
    severity,
    category,
    message,
    confidence,
    evidence=None
):
    """
    Creates a standard flag object.
    """
    return {
        "severity": severity,
        "category": category,
        "message": message,
        "confidence": round(float(confidence), 2),
        "evidence": evidence or {}
    }
# ---------------------------------------------------------
# DATE FUNCTIONS
# ---------------------------------------------------------
def parse_date(date_string):
    """
    Attempts to convert different date formats
    into a Python date object.
    """
    if not date_string:
        return None
    date_string = str(date_string).strip()
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(
                date_string,
                fmt
            ).date()
        except ValueError:
            continue
    return None
# ---------------------------------------------------------
# CHECK DATE VALIDITY
# ---------------------------------------------------------
def check_date_validity(doc):
    """
    Checks whether issue_date is a valid date
    and whether it is a future date.
    """
    fields = doc.get("fields", {})
    issue_date = fields.get("issue_date")
    if not issue_date:
        return []
    parsed_date = parse_date(issue_date)
    if parsed_date is None:
        return [
            create_flag(
                "MEDIUM",
                "INVALID_DATE",
                f"Invalid issue date: {issue_date}",
                1.0,
                {
                    "field": "issue_date",
                    "value": issue_date
                }
            )
        ]
    if parsed_date > date.today():
        return [
            create_flag(
                "MEDIUM",
                "FUTURE_DATE",
                f"Issue date cannot be in the future: {issue_date}",
                1.0,
                {
                    "field": "issue_date",
                    "value": issue_date
                }
            )
        ]
    return []
# ---------------------------------------------------------
# CHECK EXPIRY
# ---------------------------------------------------------
def check_expiry(doc):
    """
    Checks whether a document has exceeded
    its configured validity period.
    """
    doc_type = doc.get("doc_type")
    fields = doc.get("fields", {})
    issue_date = fields.get("issue_date")
    validity_days = VALIDITY_DAYS.get(doc_type)
    # Document does not have an expiry rule.
    if validity_days is None:
        return []
    if not issue_date:
        return []
    parsed_date = parse_date(issue_date)
    if parsed_date is None:
        return []
    age = (date.today() - parsed_date).days
    if age > validity_days:
        return [
            create_flag(
                "HIGH",
                "EXPIRED_DOCUMENT",
                (
                    f"{doc_type.replace('_', ' ').title()} "
                    f"has exceeded its configured validity period"
                ),
                1.0,
                {
                    "issue_date": issue_date,
                    "age_days": age,
                    "validity_days": validity_days
                }
            )
        ]
    return []
# ---------------------------------------------------------
# CHECK MISSING FIELDS
# ---------------------------------------------------------
def check_missing_fields(doc):
    doc_type = doc.get("doc_type")
    fields = doc.get("fields", {})
    required_fields = REQUIRED_FIELDS.get(
        doc_type,
        []
    )
    flags = []
    for field in required_fields:
        value = fields.get(field)
        if value is None or str(value).strip() == "":
            flags.append(
                create_flag(
                    "MEDIUM",
                    "MISSING_FIELD",
                    (
                        f"Required field '{field}' "
                        f"is missing from {doc_type.replace('_', ' ')}"
                    ),
                    1.0,
                    {
                        "field": field
                    }
                )
            )
    return flags
# ---------------------------------------------------------
# CHECK CERTIFICATE ID FORMAT
# ---------------------------------------------------------
def check_certificate_id(doc):
    doc_type = doc.get("doc_type")
    fields = doc.get("fields", {})
    certificate_id = fields.get(
        "certificate_id"
    )
    if not certificate_id:
        return []
    pattern = CERTIFICATE_PATTERNS.get(
        doc_type
    )
    # No format rule for this document.
    if pattern is None:
        return []
    if not re.match(
        pattern,
        str(certificate_id).strip()
    ):

        return [
            create_flag(
                "MEDIUM",
                "INVALID_CERTIFICATE_ID",
                (
                    f"Certificate number '{certificate_id}' "
                    f"does not follow the expected format"
                ),
                1.0,
                {
                    "certificate_id": certificate_id
                }
            )
        ]

    return []
# ---------------------------------------------------------
# CHECK INCOME
# ---------------------------------------------------------
def check_income(doc):

    fields = doc.get("fields", {})

    income = fields.get(
        "income_amount"
    )

    if income is None:
        return []

    try:

        # Remove currency symbols and commas.
        cleaned = str(income)
        cleaned = cleaned.replace(
            "₹",
            ""
        )
        cleaned = cleaned.replace(
            ",",
            ""
        )
        cleaned = cleaned.strip()

        amount = float(cleaned)

        if amount < 0:

            return [
                create_flag(
                    "HIGH",
                    "INVALID_INCOME",
                    "Income amount cannot be negative",
                    1.0,
                    {
                        "income_amount": income
                    }
                )
            ]

    except ValueError:

        return [
            create_flag(
                "MEDIUM",
                "INVALID_INCOME",
                f"Income amount could not be interpreted: {income}",
                1.0,
                {
                    "income_amount": income
                }
            )
        ]
    return []
# ---------------------------------------------------------
# MAIN SINGLE DOCUMENT CHECK
# ---------------------------------------------------------
def check_document(doc):
    flags = []
    flags.extend(
        check_missing_fields(doc)
    )
    flags.extend(
        check_date_validity(doc)
    )
    flags.extend(
        check_expiry(doc)
    )
    flags.extend(
        check_certificate_id(doc)
    )
    flags.extend(
        check_income(doc)
    )
    return flags