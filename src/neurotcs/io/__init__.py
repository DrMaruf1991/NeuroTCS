"""NeuroTCS universal dataset I/O (v1.24.0).

Read real-world dataset files into pandas DataFrames so any user can audit
their data, then map declared columns to the orchestrator submission.

Fail-closed by design (the NeuroTCS contract):
  * unknown file types raise (never guessed),
  * PDF extraction is OFF by default and best-effort when enabled,
  * column mapping is EXPLICIT; a missing required column raises rather than
    being inferred. The auditor must never audit data it had to guess about.
"""
from neurotcs.io.readers import (  # noqa: F401
    AmbiguousInputError,
    PdfExtractionError,
    UnsupportedFormatError,
    describe_tables,
    read_tables,
    tables_to_submission,
)

__all__ = [
    "read_tables",
    "describe_tables",
    "tables_to_submission",
    "UnsupportedFormatError",
    "PdfExtractionError",
    "AmbiguousInputError",
]
