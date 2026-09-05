from rules_engine import process_application
# =========================================================
# TEST APPLICATION
# =========================================================
application = {
    "application_id": "APP-2026-8891",
    "applicant_name": "Priya Sharma",
    "documents": [
        # -------------------------------------------------
        # INCOME CERTIFICATE
        # -------------------------------------------------
        {
            "doc_type": "income_certificate",
            "fields": {
                "name": "Priya Sharma",
                "dob": "12-05-2006",
                "father_name": "Raj Sharma",
                "address": "12 Green Park Delhi",
                "income_amount": "50000",
                # Old date → should trigger expiry
                "issue_date": "2024-03-15",
                "certificate_id": "INC12345"
            },
            "tampering_detected": False
        },
        # -------------------------------------------------
        # CATEGORY CERTIFICATE
        # -------------------------------------------------
        {
            "doc_type": "category_certificate",
            "fields": {
                # Intentional typo
                "name": "Priya Sharna",

                "dob": "12-05-2006",

                "father_name": "Raj Sharma",

                "address": "12 Green Park Delhi",

                "issue_date": "2026-01-10",

                "certificate_id": "CAT12345"
            },

            "tampering_detected": False
        },


        # -------------------------------------------------
        # MARKSHEET
        # -------------------------------------------------

        {
            "doc_type": "marksheet",

            "fields": {

                "name": "Priya Sharma",

                "dob": "12-05-2006",

                "father_name": "Raj Sharma",

                "address": "12 Green Park Delhi"
            },

            "tampering_detected": False
        },


        # -------------------------------------------------
        # APPLICATION FORM
        # -------------------------------------------------

        {
            "doc_type": "application_form",

            "fields": {

                "name": "Priya Sharma",

                "dob": "12-05-2006",

                "father_name": "Raj Sharma",

                "address": "12 Green Park Delhi",

                # Intentional income mismatch
                "income_amount": "60000"
            },

            "tampering_detected": False
        }
    ]
}


# =========================================================
# RUN
# =========================================================

result = process_application(
    application
)


# =========================================================
# DISPLAY
# =========================================================

print("\n====================================")
print("       RULE ENGINE RESULT")
print("====================================\n")

print(
    "Application:",
    result["application_id"]
)

print(
    "Number of flags:",
    len(result["flags"])
)

print()


for i, flag in enumerate(
    result["flags"],
    start=1
):

    print(
        f"{i}. [{flag['severity']}] "
        f"{flag['category']}"
    )

    print(
        f"   {flag['message']}"
    )

    print(
        f"   Confidence: "
        f"{flag['confidence']}"
    )

    print()