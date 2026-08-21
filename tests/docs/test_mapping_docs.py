"""Guard tests: every shipped trajectory adapter has a label-mapping doc
(external expert review, 2026-08).

Reviewer ask: "documenting the mapping for each dataset, since ADNI, NACC,
OASIS, etc. don't necessarily define these clinical categories in exactly
the same way. That may end up being a really important part of the work."

Each doc must name the actual source variables the adapter consumes, so the
documentation cannot silently drift away from the code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPPINGS = _REPO_ROOT / "docs" / "mappings"

# cohort doc -> tokens that must appear (the adapter's real source variables)
_REQUIRED = {
    "oasis3.md": ["CDRTOT", "CN", "MCI", "AD", "0.5"],
    "adni.md": ["DIAGNOSIS", "DXSUM", "Dementia", "EXAMDATE"],
    "nacc.md": ["NACCUDSD", "CDRGLOB", "VISITDATE"],
    "miriad.md": ["MMSE", "27", "18"],
}


def test_mappings_index_exists():
    assert (_MAPPINGS / "README.md").exists(), (
        "docs/mappings/README.md missing — per-cohort label-mapping "
        "documentation is a load-bearing deliverable (expert review 2026-08)"
    )


@pytest.mark.parametrize("doc,tokens", sorted(_REQUIRED.items()))
def test_cohort_mapping_doc_exists_and_names_source_variables(doc, tokens):
    path = _MAPPINGS / doc
    assert path.exists(), f"docs/mappings/{doc} missing"
    text = path.read_text(encoding="utf-8")
    for token in tokens:
        assert token in text, (
            f"docs/mappings/{doc} must document source variable/threshold "
            f"'{token}' used by the adapter"
        )
    # every mapping doc must confront the reviewer's core concern
    assert "artifact" in text.lower(), (
        f"docs/mappings/{doc} must discuss mapping artifacts as a "
        f"false-positive source for flags"
    )
