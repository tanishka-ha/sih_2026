"""
Tests for SQLite Database Persistence
=====================================
Validates table creation and CRUD operations for applications, documents, fields, and flags.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import (
    Base,
    ApplicationModel,
    DocumentModel,
    ExtractedFieldModel,
    FlagModel,
    VerificationRunModel,
)


def test_database_crud():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Insert Application
    app = ApplicationModel(
        application_id="APP-TEST-DB",
        status="COMPLETED_WITH_FLAGS",
        applicant_name="Priya Sharma",
    )
    session.add(app)
    session.commit()

    # 2. Insert Document
    doc = DocumentModel(
        document_id="DOC-01",
        application_id="APP-TEST-DB",
        document_type="income_certificate",
        original_filename="income.pdf",
        original_path="/tmp/income.pdf",
        page_count=1,
    )
    session.add(doc)

    # 3. Insert Extracted Field
    field = ExtractedFieldModel(
        document_id="DOC-01",
        page_number=1,
        field_name="income_amount",
        raw_value="50000",
        normalized_value="50000",
        confidence=0.95,
    )
    session.add(field)

    # 4. Insert Flag
    flag = FlagModel(
        flag_id="FLAG-001",
        application_id="APP-TEST-DB",
        document_id="DOC-01",
        severity="HIGH",
        category="INCOME_LIMIT_EXCEEDED",
        message="Income too high",
        source="ROLE_2",
    )
    session.add(flag)
    session.commit()

    # Query back and assert
    queried_app = session.query(ApplicationModel).filter_by(application_id="APP-TEST-DB").first()
    assert queried_app is not None
    assert len(queried_app.documents) == 1
    assert len(queried_app.flags) == 1
    assert len(queried_app.documents[0].fields) == 1
    assert queried_app.documents[0].fields[0].field_name == "income_amount"

    session.close()
