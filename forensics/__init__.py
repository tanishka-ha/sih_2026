"""
Document Forensics Analysis Package
====================================
Detects visual pixel tampering and digital header manipulation
in submitted document bundles.
"""

from forensics.analyzer import DocumentForensicsAnalyzer, analyze_document_forensics

__version__ = "1.0.0"
__all__ = ["DocumentForensicsAnalyzer", "analyze_document_forensics"]
