from rapidfuzz.fuzz import token_sort_ratio
from single_doc_rules import create_flag


# ---------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------

def normalize_text(value):

    if value is None:
        return ""

    return " ".join(
        str(value)
        .lower()
        .strip()
        .split()
    )


# ---------------------------------------------------------
# NAME SIMILARITY
# ---------------------------------------------------------

def compare_names(name1, name2):

    name1 = normalize_text(name1)
    name2 = normalize_text(name2)

    if not name1 or not name2:
        return 0

    return token_sort_ratio(
        name1,
        name2
    )


# ---------------------------------------------------------
# GENERIC FUZZY FIELD CHECK
# ---------------------------------------------------------

def check_fuzzy_field(
    documents,
    field_name,
    field_label
):

    values = []

    for doc in documents:

        fields = doc.get(
            "fields",
            {}
        )

        value = fields.get(
            field_name
        )

        if value:

            values.append(
                {
                    "doc_type": doc.get(
                        "doc_type"
                    ),
                    "value": value
                }
            )

    flags = []

    if len(values) < 2:
        return flags

    # Compare every document against the first
    # reference document.
    reference = values[0]

    for current in values[1:]:

        score = compare_names(
            reference["value"],
            current["value"]
        )

        # ---------------------------------------------
        # MATCH
        # ---------------------------------------------

        if score >= 95:
            continue

        # ---------------------------------------------
        # LIKELY TYPO / OCR ERROR
        # ---------------------------------------------

        elif score >= 80:

            flags.append(
                create_flag(
                    "MEDIUM",
                    "CROSS_DOC_MISMATCH",
                    (
                        f"{field_label} differs between "
                        f"{reference['doc_type']} "
                        f"('{reference['value']}') and "
                        f"{current['doc_type']} "
                        f"('{current['value']}'). "
                        f"Similarity: {score:.0f}% — "
                        f"likely typo or OCR error."
                    ),
                    score / 100,
                    {
                        "field": field_name,
                        "document_1": reference["doc_type"],
                        "document_2": current["doc_type"],
                        "value_1": reference["value"],
                        "value_2": current["value"],
                        "similarity": round(score, 2)
                    }
                )
            )

        # ---------------------------------------------
        # STRONG MISMATCH
        # ---------------------------------------------

        else:

            flags.append(
                create_flag(
                    "HIGH",
                    "NAME_MISMATCH",
                    (
                        f"{field_label} mismatch between "
                        f"{reference['doc_type']} "
                        f"('{reference['value']}') and "
                        f"{current['doc_type']} "
                        f"('{current['value']}'). "
                        f"Similarity: {score:.0f}%."
                    ),
                    score / 100,
                    {
                        "field": field_name,
                        "document_1": reference["doc_type"],
                        "document_2": current["doc_type"],
                        "value_1": reference["value"],
                        "value_2": current["value"],
                        "similarity": round(score, 2)
                    }
                )
            )

    return flags


# ---------------------------------------------------------
# EXACT FIELD CHECK
# ---------------------------------------------------------

def check_exact_field(
    documents,
    field_name,
    field_label
):

    values = []

    for doc in documents:

        value = doc.get(
            "fields",
            {}
        ).get(field_name)

        if value:

            values.append(
                {
                    "doc_type": doc.get(
                        "doc_type"
                    ),
                    "value": str(value).strip()
                }
            )

    flags = []

    if len(values) < 2:
        return flags

    reference = values[0]

    for current in values[1:]:

        if (
            normalize_text(
                reference["value"]
            )
            !=
            normalize_text(
                current["value"]
            )
        ):

            flags.append(
                create_flag(
                    "HIGH",
                    "CROSS_DOC_MISMATCH",
                    (
                        f"{field_label} differs between "
                        f"{reference['doc_type']} and "
                        f"{current['doc_type']}."
                    ),
                    1.0,
                    {
                        "field": field_name,
                        "document_1": reference["doc_type"],
                        "document_2": current["doc_type"],
                        "value_1": reference["value"],
                        "value_2": current["value"]
                    }
                )
            )

    return flags


# ---------------------------------------------------------
# INCOME COMPARISON
# ---------------------------------------------------------

def normalize_income(value):

    if value is None:
        return None

    try:

        value = str(value)

        value = value.replace(
            "₹",
            ""
        )

        value = value.replace(
            ",",
            ""
        )

        return float(
            value.strip()
        )

    except ValueError:

        return None


def check_income_consistency(
    documents
):

    application_income = None
    certificate_income = None

    application_doc = None
    certificate_doc = None

    for doc in documents:

        doc_type = doc.get(
            "doc_type"
        )

        fields = doc.get(
            "fields",
            {}
        )

        # Application form
        if doc_type == "application_form":

            if fields.get(
                "income_amount"
            ):

                application_income = normalize_income(
                    fields["income_amount"]
                )

                application_doc = doc_type

        # Income certificate
        elif doc_type == "income_certificate":

            if fields.get(
                "income_amount"
            ):

                certificate_income = normalize_income(
                    fields["income_amount"]
                )

                certificate_doc = doc_type

    if (
        application_income is None
        or certificate_income is None
    ):
        return []

    if application_income != certificate_income:

        return [
            create_flag(
                "HIGH",
                "INCOME_MISMATCH",
                (
                    f"Declared income "
                    f"({application_income:,.0f}) does not "
                    f"match income certificate "
                    f"({certificate_income:,.0f})."
                ),
                1.0,
                {
                    "application_income": application_income,
                    "certificate_income": certificate_income
                }
            )
        ]

    return []


# ---------------------------------------------------------
# MAIN CROSS-DOCUMENT CHECK
# ---------------------------------------------------------

def check_cross_document(
    documents
):

    flags = []

    # Names
    flags.extend(
        check_fuzzy_field(
            documents,
            "name",
            "Name"
        )
    )

    # Father's name
    flags.extend(
        check_fuzzy_field(
            documents,
            "father_name",
            "Father's name"
        )
    )

    # DOB
    flags.extend(
        check_exact_field(
            documents,
            "dob",
            "Date of birth"
        )
    )

    # Address
    flags.extend(
        check_fuzzy_field(
            documents,
            "address",
            "Address"
        )
    )
    # Income
    flags.extend(
        check_income_consistency(
            documents
        )
    )
    return flags