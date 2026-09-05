"""
Tests for SHA-256 Hash-Chain Audit Log
======================================
Validates cryptographic block chaining and tamper detection.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from audit.audit_log import AuditLogger, AuditEventModel
from db.database import Base


def test_audit_hash_chain_integrity():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    audit = AuditLogger(session)
    app_id = "APP-AUDIT-TEST"

    # 1. Log sequential events
    ev1 = audit.log_event(app_id, "APPLICATION_CREATED", {"files": 2})
    ev2 = audit.log_event(app_id, "FILES_UPLOADED", {"names": ["doc1.pdf", "doc2.jpg"]})
    ev3 = audit.log_event(app_id, "OCR_COMPLETED", {"fields_extracted": 8})
    ev4 = audit.log_event(app_id, "VERIFICATION_COMPLETED", {"status": "COMPLETED"})

    # Check chain links
    assert ev1.previous_hash == AuditLogger.GENESIS_HASH
    assert ev2.previous_hash == ev1.current_hash
    assert ev3.previous_hash == ev2.current_hash
    assert ev4.previous_hash == ev3.current_hash

    # Verify unbroken chain
    is_valid, reason = audit.verify_chain(app_id)
    assert is_valid is True
    assert "verified successfully" in reason

    # 2. Simulate malicious record alteration (data tampering attack)
    ev2.payload_json = '{"names": ["MALICIOUS_ALTERED_DOC.pdf"]}'
    session.commit()

    # Re-verify: must fail!
    tampered_valid, tampered_reason = audit.verify_chain(app_id)
    assert tampered_valid is False
    assert "tampering detected" in tampered_reason.lower()

    session.close()
