"""
Role 2: Duplicate Certificate Checker
=====================================
Detects if a certificate_id has been observed in a previous application.
"""

try:
    from .single_doc_rules import create_flag
except ImportError:
    from single_doc_rules import create_flag

# Stores:
# certificate_id → application_id
# Example:
# INC12345 → APP001
seen_certificates = {}


def check_duplicate_certificates(
    application_id,
    documents
):
    flags = []

    for doc in documents:
        fields = doc.get(
            "fields",
            {}
        )
        certificate_id = fields.get(
            "certificate_id"
        )

        if not certificate_id:
            continue

        certificate_id = str(
            certificate_id
        ).strip()

        # ---------------------------------------------
        # DUPLICATE FOUND
        # ---------------------------------------------
        if certificate_id in seen_certificates:
            previous_application = (
                seen_certificates[
                    certificate_id
                ]
            )

            # Don't flag if it's somehow
            # the same application.
            if previous_application != application_id:
                flags.append(
                    create_flag(
                        "HIGH",
                        "DUPLICATE_CERTIFICATE",
                        (
                            f"Certificate ID "
                            f"{certificate_id} was previously "
                            f"observed in application "
                            f"{previous_application}."
                        ),
                        1.0,
                        {
                            "certificate_id": certificate_id,
                            "current_application": application_id,
                            "previous_application": previous_application
                        }
                    )
                )

        # ---------------------------------------------
        # NEW CERTIFICATE
        # ---------------------------------------------
        else:
            seen_certificates[
                certificate_id
            ] = application_id

    return flags
