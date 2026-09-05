"""
SQLAlchemy ORM Models
=====================
Stores applications, documents, extracted fields, validation flags, and runs.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from db.database import Base


class ApplicationModel(Base):
    __tablename__ = "applications"

    application_id = Column(String(64), primary_key=True, index=True)
    created_at = Column(String(64), default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(String(64), default=lambda: datetime.now(timezone.utc).isoformat())
    status = Column(String(32), default="COMPLETED")
    applicant_name = Column(String(128), default="Unknown")

    documents = relationship("DocumentModel", back_populates="application", cascade="all, delete-orphan")
    flags = relationship("FlagModel", back_populates="application", cascade="all, delete-orphan")
    runs = relationship("VerificationRunModel", back_populates="application", cascade="all, delete-orphan")


class DocumentModel(Base):
    __tablename__ = "documents"

    document_id = Column(String(64), primary_key=True, index=True)
    application_id = Column(String(64), ForeignKey("applications.application_id"), nullable=False)
    document_type = Column(String(64), nullable=False)
    original_filename = Column(String(256), nullable=False)
    original_path = Column(Text, nullable=False)
    page_count = Column(Integer, default=1)

    application = relationship("ApplicationModel", back_populates="documents")
    fields = relationship("ExtractedFieldModel", back_populates="document", cascade="all, delete-orphan")


class ExtractedFieldModel(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(64), ForeignKey("documents.document_id"), nullable=False)
    page_number = Column(Integer, default=1)
    field_name = Column(String(64), nullable=False)
    raw_value = Column(Text, nullable=True)
    normalized_value = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    bounding_box = Column(Text, nullable=True)  # JSON string

    document = relationship("DocumentModel", back_populates="fields")


class FlagModel(Base):
    __tablename__ = "flags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flag_id = Column(String(64), index=True, nullable=False)
    application_id = Column(String(64), ForeignKey("applications.application_id"), nullable=False)
    document_id = Column(String(64), nullable=True)
    severity = Column(String(16), nullable=False)
    category = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    page = Column(Integer, nullable=True)
    bounding_box = Column(Text, nullable=True)  # JSON string
    source = Column(String(32), nullable=False)  # ROLE_1 | ROLE_2 | ROLE_3 | ROLE_4
    explanation = Column(Text, nullable=True)
    created_at = Column(String(64), default=lambda: datetime.now(timezone.utc).isoformat())

    application = relationship("ApplicationModel", back_populates="flags")


class VerificationRunModel(Base):
    __tablename__ = "verification_runs"

    run_id = Column(String(64), primary_key=True, index=True)
    application_id = Column(String(64), ForeignKey("applications.application_id"), nullable=False)
    started_at = Column(String(64), nullable=False)
    completed_at = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)

    application = relationship("ApplicationModel", back_populates="runs")
