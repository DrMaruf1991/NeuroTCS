"""Version single-source-of-truth guard.

The canonical version lives in pyproject.toml (`project.version`). This test
asserts every other place that states a version agrees with it, so the four-way
drift caught by the 2026-06 real-world-readiness audit (pyproject 1.66 vs README
badge 1.33 vs SECURITY 1.1.x vs CITATION 1.17) can never silently recur.

Scope of the guard:
  - src/neurotcs/__init__.py  __version__
  - README.md version badge
  - SECURITY.md supported-versions table (latest line)
  - CITATION.cff version
  - README BibTeX `version = {...}`

Historical version mentions (CHANGELOG entries, "v1.9.0 first AD-only release",
scope-history prose, design-doc milestones) are intentionally NOT guarded: they
are immutable historical record, not claims about the current release.
"""
from __future__ import annotations

import re
from pathlib import Path

import neurotcs

_ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "could not find version in pyproject.toml"
    return m.group(1)


CANON = _pyproject_version()


def test_pyproject_is_valid_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", CANON), f"non-semver version: {CANON}"


def test_package_dunder_version_matches():
    assert neurotcs.__version__ == CANON, (
        f"__version__ {neurotcs.__version__} != pyproject {CANON}")


def test_readme_badge_matches():
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    badges = re.findall(r"badge/version-([0-9.]+?)-", readme)
    assert badges, "no version badge found in README.md"
    for b in badges:
        assert b == CANON, f"README version badge {b} != pyproject {CANON}"


def test_readme_bibtex_version_matches():
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"version\s*=\s*\{([0-9.]+)\}", readme)
    if m:  # BibTeX block is optional, but if present it must agree
        assert m.group(1) == CANON, (
            f"README BibTeX version {m.group(1)} != pyproject {CANON}")


def test_citation_cff_version_matches():
    cff = _ROOT / "CITATION.cff"
    if cff.exists():
        text = cff.read_text(encoding="utf-8")
        m = re.search(r'^version:\s*"?([0-9.]+)"?', text, re.MULTILINE)
        assert m, "CITATION.cff present but has no version field"
        assert m.group(1) == CANON, (
            f"CITATION.cff version {m.group(1)} != pyproject {CANON}")


def test_security_latest_supported_matches_minor():
    """SECURITY.md latest-supported line must reference the current minor."""
    sec = (_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    minor = ".".join(CANON.split(".")[:2])  # e.g. 1.67
    # Accept the current minor with an x patch wildcard, e.g. "1.67.x"
    assert f"{minor}.x" in sec or CANON in sec, (
        f"SECURITY.md does not reference current minor {minor}.x / {CANON}")
    # And it must NOT still advertise a stale pre-current minor as "latest".
    assert "1.1.x" not in sec, "SECURITY.md still lists stale 1.1.x as supported"
