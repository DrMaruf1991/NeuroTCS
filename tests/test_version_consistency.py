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


# --------------------------------------------------------------------------- #
# Documentation-count drift guards (added v1.68.0 after a proactive self-audit
# found README documenting "3 AD rule packs" while 6 ship, and a test-count
# badge of 1909 while 1915 pass). These guard the *class* of defect -- docs
# silently lagging a number -- not just the instances.
# --------------------------------------------------------------------------- #
def _production_ad_pack_count() -> int:
    """Derive the number of production AD rule packs from disk (not hardcoded)."""
    from neurotcs.rulepack.loader import load_rulepack
    ad_dir = _ROOT / "src" / "neurotcs" / "rulepack" / "rules" / "ad"
    count = 0
    for yaml_path in sorted(ad_dir.glob("*.yaml")):
        pid = "ad/" + yaml_path.stem
        if load_rulepack(pid).is_production:
            count += 1
    return count


def test_readme_documents_correct_ad_pack_count():
    """README's '<N> production AD rule packs' prose must match reality."""
    n = _production_ad_pack_count()
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    # Accept either digit or small-number word for the count in the scope prose.
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
             6: "six", 7: "seven", 8: "eight"}
    pattern = rf"\b({n}|{words.get(n, n)}) (production )?AD rule packs?\b"
    assert re.search(pattern, readme), (
        f"README does not state the correct AD rule-pack count "
        f"({n} production packs ship); update the scope prose.")


def test_readme_table_lists_every_production_ad_pack():
    """Every shipped production AD pack must appear in the README pack table."""
    from neurotcs.rulepack.loader import load_rulepack
    ad_dir = _ROOT / "src" / "neurotcs" / "rulepack" / "rules" / "ad"
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    missing = []
    for yaml_path in sorted(ad_dir.glob("*.yaml")):
        pid = "ad/" + yaml_path.stem
        if not load_rulepack(pid).is_production:
            continue
        # the table references packs as `ad/<name>@<ver>`; require the id stem
        if f"ad/{yaml_path.stem}" not in readme:
            missing.append(pid)
    assert not missing, (
        f"README pack table omits production packs: {missing}")


def test_readme_test_count_badge_and_prose_agree():
    """The README test-count badge and the 'expect N passed' prose must agree
    with each other (internal consistency), so a badge/prose split like the
    1909-vs-1915 drift cannot recur silently. The exact live count is not
    hard-pinned here (that would be self-referential and flaky); this asserts
    the documented numbers are mutually consistent."""
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    badge = re.findall(r"badge/tests-(\d+)%20passed", readme)
    prose = re.findall(r"expect (\d+)(?:\+cohort)? (?:passed|tests passed)", readme)
    env_line = re.findall(r"\*\*(\d+) passed / \d+ skipped\*\*", readme)
    documented = set(badge) | set(prose) | set(env_line)
    assert documented, "no documented test counts found in README"
    assert len(documented) == 1, (
        f"README test counts disagree across badge/prose/env-line: {documented}")


# --------------------------------------------------------------------------- #
# Release-readiness guards (added v1.69.0). Keep the release docs and the build
# configuration mutually consistent so a release can't ship with a doc that
# references a package name, extra, or entrypoint that does not exist.
# --------------------------------------------------------------------------- #
def _pyproject_text() -> str:
    return (_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_quickstart_doc_exists_and_uses_real_package_name():
    qs = _ROOT / "docs" / "QUICKSTART.md"
    assert qs.exists(), "docs/QUICKSTART.md missing (release deliverable)"
    text = qs.read_text(encoding="utf-8")
    assert "pip install neurotcs" in text or "neurotcs-" in text, (
        "QUICKSTART must show the real install command")
    # the honest scope banner must be present (no silent overclaim)
    assert "research instrument" in text.lower()
    assert "not" in text.lower() and "clinical" in text.lower()


def test_releasing_doc_exists():
    assert (_ROOT / "docs" / "RELEASING.md").exists(), (
        "docs/RELEASING.md missing (release process deliverable)")


def test_documented_optional_extras_exist_in_pyproject():
    """Any `neurotcs[<extra>]` referenced in the quickstart must be a real
    optional-dependency extra in pyproject.toml."""
    qs = (_ROOT / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")
    referenced = set(re.findall(r"neurotcs\[([a-z0-9_]+)\]", qs))
    pyproject = _pyproject_text()
    declared = set(re.findall(r"^([a-z0-9_]+)\s*=\s*\[", pyproject, re.MULTILINE))
    missing = referenced - declared
    assert not missing, (
        f"QUICKSTART references undeclared extras {missing}; "
        f"declared extras are {declared}")


def test_console_entrypoint_declared():
    """The `neurotcs` CLI documented in the quickstart must be a real
    console-script entry point."""
    pyproject = _pyproject_text()
    assert "neurotcs =" in pyproject and "cli:main" in pyproject, (
        "neurotcs console-script entry point not declared in pyproject.toml")


# --------------------------------------------------------------------------- #
# Optional-dependency import hygiene (added v1.69.0 after a clean-machine
# install revealed 3 tests bare-importing pyreadr before their skip logic,
# crashing instead of skipping when the optional `radni` extra was absent).
# Tests may use an optional dependency only via pytest.importorskip or inside a
# try/except ImportError -- never a bare top-of-function `import <optional>`
# that runs before the skip guard.
#
# As of v1.73.0, pyreadr (R) and pyreadstat (SPSS) are CORE dependencies, so
# they are no longer policed here. pdfplumber stays optional (PDF is a gated
# opt-in by design) and remains guarded.
# --------------------------------------------------------------------------- #
def test_no_bare_optional_dependency_import_in_tests():
    import ast

    tests_dir = _ROOT / "tests"
    optional_mods = {"pdfplumber"}
    offenders = []

    for py in tests_dir.rglob("test_*.py"):
        # utf-8-sig tolerates a leading BOM (some files carry one on Windows)
        src = py.read_text(encoding="utf-8-sig")
        # Collect line numbers that are inside a try-block, so try/except
        # ImportError guarded imports are allowed.
        tree = ast.parse(src, filename=str(py))
        guarded_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for stmt in ast.walk(node):
                    if hasattr(stmt, "lineno"):
                        guarded_lines.add(stmt.lineno)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in optional_mods and node.lineno not in guarded_lines:
                        offenders.append(f"{py.relative_to(_ROOT)}:{node.lineno} "
                                         f"bare import {alias.name}")
    assert not offenders, (
        "Optional dependencies must be imported via pytest.importorskip or "
        "inside try/except ImportError, never bare (they crash on a clean "
        "install without the optional extra):\n  " + "\n  ".join(offenders))


def _current_minor() -> str:
    # '1.80.0' -> '1.80'
    parts = CANON.split(".")
    return ".".join(parts[:2])


def test_security_floor_row_matches_current_minor():
    """SECURITY.md support table: both the (latest) row AND the floor row
    must track the current minor. The floor row was NOT guarded before, which
    let a 1.80.0 bump ship '1.80.x (latest)' next to a stale '< 1.79' floor.
    """
    sec = (_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    minor = _current_minor()
    assert f"{minor}.x (latest)" in sec, (
        f"SECURITY.md missing '{minor}.x (latest)' row for current minor")
    assert f"< {minor} " in sec or f"< {minor}\n" in sec, (
        f"SECURITY.md floor row does not say '< {minor}' "
        f"(stale floor would mislead users about supported versions)")


def test_changelog_has_current_version_entry():
    """CHANGELOG.md must carry an entry for the current version. The 1.80.0
    bump aborted before prepending its entry; nothing caught the omission.
    """
    cl = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{CANON}]" in cl, (
        f"CHANGELOG.md has no '## [{CANON}]' entry for the current release")
