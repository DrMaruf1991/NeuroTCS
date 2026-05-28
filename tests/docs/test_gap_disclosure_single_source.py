"""Gap-disclosure single-source-of-truth guard (v1.20.0).

The README and the datasheet once maintained two separate, unsynchronized
gap lists (README: 13 items; datasheet Section F: 6 items) that had drifted
apart. This test enforces the structural fix: the datasheet Section F is the
ONE authoritative gap list, and the README points to it rather than
duplicating a list or a hardcoded count (which would drift again).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
DATASHEET = ROOT / "docs" / "datasheet" / "ad_neurotcs_datasheet.md"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _datasheet() -> str:
    return DATASHEET.read_text(encoding="utf-8")


def test_readme_has_no_hardcoded_gap_count():
    """README must not assert 'N open gaps' -- a hardcoded count drifts."""
    m = re.search(r"\d+\s+open\s+gaps", _readme())
    assert m is None, (
        f"README contains a hardcoded gap count ({m.group(0)!r}). The gap "
        f"count must live only in datasheet Section F, not be duplicated in "
        f"the README where it drifts. Point to Section F instead."
    )


def test_readme_points_to_datasheet_section_f():
    """README limitations must reference the datasheet as the source."""
    c = _readme()
    assert "Known limitations" in c, "README lost its limitations section"
    assert "ad_neurotcs_datasheet.md" in c, (
        "README limitations must link to the datasheet (single source)"
    )
    assert "Section F" in c, "README must point to datasheet Section F by name"


def test_readme_does_not_duplicate_gap_list():
    """README must not re-enumerate the gaps (no parallel numbered list of
    known stale items)."""
    c = _readme()
    # The old parallel list contained these signature phrases; none should remain.
    for stale in ("PMIDs pending", "Single-rater attestation",
                  "macOS cross-platform reproducibility not yet observed"):
        assert stale not in c, (
            f"README still duplicates gap-list item {stale!r}. Gaps live only "
            f"in datasheet Section F."
        )


def test_datasheet_section_f_is_authoritative_and_nonempty():
    """Datasheet Section F must exist, declare itself the source of truth,
    and contain an Open gaps subsection."""
    c = _datasheet()
    assert "## F " in c, "Datasheet Section F missing"
    assert "single source of truth" in c, (
        "Section F must declare itself the single source of truth"
    )
    assert "### Open gaps" in c, "Section F must have an Open gaps subsection"
    # at least one numbered open gap present
    f_start = c.index("## F ")
    f_end = c.index("## G ", f_start) if "## G " in c[f_start:] else len(c)
    section_f = c[f_start:f_end]
    assert re.search(r"^\s*1\.\s+\*\*", section_f, re.MULTILINE), (
        "Section F Open gaps must be a numbered list"
    )


def test_readme_core_sections_intact():
    """Guard against edit scripts silently deleting core README sections.
    A v1.20.0 edit double-run once removed the License + Contact sections
    while gap tests stayed green -- this assertion closes that hole."""
    c = _readme()
    for section in ("## Known limitations", "## License", "## Contact"):
        assert section in c, f"README missing required section: {section!r}"
    assert "Apache 2.0" in c, "README License body (Apache 2.0) missing"
