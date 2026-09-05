"""
Cryptographic SHA-256 Hash-Chain Audit Log
==========================================
Provides tamper-evident auditing for document verification lifecycle events.
Every event is cryptographically sealed into a hash chain:
current_hash = SHA-256(previous_hash + timestamp + application_id + action + payload_hash)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import Session

from db.database import Base


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=False)
    current_hash = Column(String(64), nullable=False)
    payload_json = Column(Text, nullable=False)


class AuditLogger:
    GENESIS_HASH: str = "0" * 64

    def __init__(self, db_session: Session):
        self.db = db_session

    @staticmethod
    def _compute_sha256(data: str) -> str:
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def log_event(
        self,
        application_id: str,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AuditEventModel:
        """Append a new verified block to the hash chain for this application."""
        # 1. Fetch latest event for this application to find previous_hash
        last_event = (
            self.db.query(AuditEventModel)
            .filter(AuditEventModel.application_id == application_id)
            .order_by(AuditEventModel.event_id.desc())
            .first()
        )

        previous_hash = last_event.current_hash if last_event else self.GENESIS_HASH
        timestamp = datetime.now(timezone.utc).isoformat()
        canonical_payload = json.dumps(payload or {}, sort_keys=True)
        payload_hash = self._compute_sha256(canonical_payload)

        # 2. Compute cryptographically sealed current hash
        raw_chain_string = f"{previous_hash}|{timestamp}|{application_id}|{action}|{payload_hash}"
        current_hash = self._compute_sha256(raw_chain_string)

        event = AuditEventModel(
            application_id=application_id,
            timestamp=timestamp,
            action=action,
            previous_hash=previous_hash,
            current_hash=current_hash,
            payload_json=canonical_payload,
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_audit_trail(self, application_id: str) -> List[Dict[str, Any]]:
        """Retrieve the chronological audit trail for an application."""
        events = (
            self.db.query(AuditEventModel)
            .filter(AuditEventModel.application_id == application_id)
            .order_by(AuditEventModel.event_id.asc())
            .all()
        )
        return [
            {
                "event_id": e.event_id,
                "application_id": e.application_id,
                "timestamp": e.timestamp,
                "action": e.action,
                "previous_hash": e.previous_hash,
                "current_hash": e.current_hash,
                "payload": json.loads(e.payload_json),
            }
            for e in events
        ]

    def verify_chain(self, application_id: str) -> Tuple[bool, str]:
        """Cryptographically verify the integrity of the audit hash chain."""
        events = (
            self.db.query(AuditEventModel)
            .filter(AuditEventModel.application_id == application_id)
            .order_by(AuditEventModel.event_id.asc())
            .all()
        )

        if not events:
            return True, "No audit events recorded for this application."

        expected_previous_hash = self.GENESIS_HASH

        for i, event in enumerate(events):
            # Check 1: Chain continuity
            if event.previous_hash != expected_previous_hash:
                return False, (
                    f"Hash chain broken at event #{event.event_id} ({event.action}): "
                    f"expected previous_hash '{expected_previous_hash}' but found '{event.previous_hash}'."
                )

            # Check 2: Recompute current hash
            payload_hash = self._compute_sha256(event.payload_json)
            raw_chain_string = f"{event.previous_hash}|{event.timestamp}|{event.application_id}|{event.action}|{payload_hash}"
            recomputed_hash = self._compute_sha256(raw_chain_string)

            if recomputed_hash != event.current_hash:
                return False, (
                    f"Data tampering detected at event #{event.event_id} ({event.action}): "
                    f"recomputed hash '{recomputed_hash}' does not match stored hash '{event.current_hash}'."
                )

            expected_previous_hash = event.current_hash

        return True, f"Audit chain verified successfully ({len(events)} blocks validated)."
