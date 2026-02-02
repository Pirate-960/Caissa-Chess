"""
engine/__init__.py

CAISSA engine module initialization.
"""

from engine.legality import LegalityValidator, LegalityReport

__all__ = [
    "LegalityValidator",
    "LegalityReport",
]
