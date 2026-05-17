"""
Pytest configuration for the NeuroTCS test suite.

This conftest.py is at the repo root. It ensures the `src/` directory is on
sys.path so the `neurotcs` namespace package imports work without requiring
a pip install. In CI we *do* `pip install -e .`, which makes the package
importable without this conftest, but this lets `python -m pytest` work
out-of-the-box for contributors.
"""

import sys
from pathlib import Path

# Put src/ on sys.path so `import neurotcs` works.
SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
