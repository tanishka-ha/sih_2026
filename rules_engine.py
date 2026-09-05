from single_doc_rules import check_document
from cross_doc_rules import check_cross_document
from duplicate_checker import check_duplicate_certificates


# ---------------------------------------------------------
# SEVERITY PRIORITY
# ---------------------------------------------------------

SEVERITY_RANK = {
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1
}


# ---------------------------------------------------------
# MAIN RULE ENGINE
# ---------------------------------------------------------

def run_rules(application):

    documents = application.get(
        "documents",
        []
    )

    application_id = application.get(
        "application_id",
        "UNKNOWN"
    )

    flags = []

    # -----------------------------------------------------
    # STEP 1
    # Single document checks
    # -----------------------------------------------------

    for document in documents:

        document_flags = check_document(
            document
        )

        flags.extend(
            document_flags
        )

    # -----------------------------------------------------
    # STEP 2
    # Cross-document checks
    # -----------------------------------------------------

    cross_document_flags = (
        check_cross_document(
            documents
        )
    )

    flags.extend(
        cross_document_flags
    )

    # -----------------------------------------------------
    # STEP 3
    # Duplicate certificate detection
    # -----------------------------------------------------

    duplicate_flags = (
        check_duplicate_certificates(
            application_id,
            documents
        )
    )

    flags.extend(
        duplicate_flags
    )

    # -----------------------------------------------------
    # STEP 4
    # Rank flags
    # -----------------------------------------------------

    flags.sort(
        key=lambda flag: (
            SEVERITY_RANK.get(
                flag["severity"],
                0
            ),
            flag.get(
                "confidence",
                0
            )
        ),
        reverse=True
    )

    return flags


# ---------------------------------------------------------
# OPTIONAL: COMPLETE RESULT
# ---------------------------------------------------------

def process_application(application):

    flags = run_rules(
        application
    )

    return {
        "application_id": application.get(
            "application_id"
        ),

        "flags": flags
    }