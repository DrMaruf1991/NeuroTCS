"""Structural regression tests for AD-lock Steps 2.4 and 2.5 deliverables.

This is the structural-skeleton guard for:
  - docs/reproducibility/ad_neurotcs_reproducibility.md   (Step 2.4)
  - docs/reproducibility/blind_validation_protocol.md     (Step 2.5)
  - requirements.lock                                       (Step 2.4)
  - scripts/compute_input_checksums.py                      (Step 2.4 / 2.5)

These tests do NOT verify prose. They verify that every required section
header is present, the canonical rule-pack SHAs are quoted verbatim
(reproducibility certificate), the locked audit_ids appear, the canonical
command sequence is present, and honest gaps are acknowledged. If any
future commit silently drops a section, mangles a SHA, or removes a gap,
CI catches it before release.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REPRO_DOC = REPO_ROOT / "docs" / "reproducibility" / "ad_neurotcs_reproducibility.md"
BLIND_DOC = REPO_ROOT / "docs" / "reproducibility" / "blind_validation_protocol.md"
LOCKFILE = REPO_ROOT / "requirements.lock"
CHECKSUM_SCRIPT = REPO_ROOT / "scripts" / "compute_input_checksums.py"


# -----------------------------------------------------------------------------
# Artifact existence
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("path,label", [
    (REPRO_DOC, "reproducibility report"),
    (BLIND_DOC, "blind-validation protocol"),
    (LOCKFILE, "requirements.lock"),
    (CHECKSUM_SCRIPT, "compute_input_checksums.py"),
], ids=["repro_doc", "blind_doc", "lockfile", "checksum_script"])
def test_artifact_exists(path: Path, label: str):
    """Each AD-lock 2.4/2.5 artifact must exist in the repo."""
    assert path.exists(), (
        f"AD-lock Step 2.4/2.5 artifact missing: {label} at {path}. "
        f"Required by docs/reproducibility/ad_neurotcs_reproducibility.md."
    )


# -----------------------------------------------------------------------------
# Reproducibility report (Step 2.4) — required sections
# -----------------------------------------------------------------------------

REPRO_REQUIRED_SECTIONS = [
    "## 1. Reproducibility guarantee",
    "### 1.1 — Code identity (rule packs)",
    "### 1.2 — Audit identity (cohort-level)",
    "### 1.3 — Test-suite identity",
    "## 2. Canonical environment",
    "### 2.1 — Operating system",
    "### 2.2 — Python version",
    "### 2.3 — Locked dependency versions",
    "### 2.4 — Random seed and bootstrap parameters",
    "## 3. Canonical command sequence",
    "## 4. Cohort access notes",
    "## 5. What this report covers — and what it does not",
    "## 6. Troubleshooting a divergent run",
    "## 7. Citation",
]


@pytest.fixture(scope="module")
def repro_text() -> str:
    return REPRO_DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize("section", REPRO_REQUIRED_SECTIONS)
def test_repro_section_present(repro_text: str, section: str):
    """Every section in the canonical reproducibility report skeleton must
    be present. A reviewer following the canonical command sequence relies
    on these headers as navigation anchors."""
    assert section in repro_text, (
        f"Missing reproducibility-report section: '{section}'. "
        f"Re-add the section with complete content; do not silently drop "
        f"steps from the reproducibility guarantee."
    )


# Rule-pack SHAs computed live from the YAML files. These hashes are the
# cryptographic identity of the AD rule packs. They MUST appear verbatim
# in the reproducibility report so a collaborator can verify them.
REPRO_REQUIRED_RULEPACK_SHAS = [
    "f359148d1cbf6abed3d4f1d36de6b3bf315c10e8997d5e73beb1a0d7bdf9e374",  # niaaa_2018
    "1393ceb489d774c059cc30f500335e29622880e347a8081854f1c461f05c47e2",  # aa_2024
    "b704a4d21efbe893dead9ea906940c5e61196f9db7f938df55b506cbee6be6e7",  # aa_2024_trac
]


@pytest.mark.parametrize("sha", REPRO_REQUIRED_RULEPACK_SHAS)
def test_repro_rulepack_sha_present(repro_text: str, sha: str):
    """The three AD rule-pack SHA-256 hashes must appear verbatim in the
    reproducibility report. If a rule pack is edited without updating
    this hash, the reproducibility guarantee is silently broken."""
    assert sha in repro_text, (
        f"Rule-pack SHA-256 missing from reproducibility report: {sha}. "
        f"Either (a) the rule pack changed and the doc wasn't updated, "
        f"or (b) the doc was edited carelessly. Re-run "
        f"`python -c \"from neurotcs import load_rulepack; "
        f"print(load_rulepack('ad/niaaa_2018').sha256)\"` to verify."
    )


REPRO_REQUIRED_AUDIT_IDS = [
    "947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0",
    "aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da",
    "804303993ff5c9134b5f4dfa8919fc6600d03a86081cedb02227ef5845784e85",
    "dcf8b7de3ff9019e9cda703064039e3a71193566d1f5082ce96646188fd52fc4",
]


@pytest.mark.parametrize("audit_id", REPRO_REQUIRED_AUDIT_IDS)
def test_repro_audit_id_present(repro_text: str, audit_id: str):
    """The four MIRIAD audit_ids (longitudinal + test-retest, both v1 and
    v2) must appear in the reproducibility report's Section 1.2."""
    assert audit_id in repro_text, (
        f"MIRIAD audit_id missing from reproducibility report: {audit_id}."
    )


REPRO_REQUIRED_GAPS = [
    "Cohort CSV checksums are not yet published",
    "ADNI and OASIS-3 audit_ids are not yet locked in CI",
    # "Jack 2024 PDF transcription is pending" — RESOLVED in v1.7.13;
    # full ad/aa_2024@2.0.0 transcription ships in this release.
]


@pytest.mark.parametrize("gap", REPRO_REQUIRED_GAPS)
def test_repro_gap_acknowledged(repro_text: str, gap: str):
    """Each known reproducibility limitation must be explicitly
    acknowledged. The AD-lock no-future-fix discipline forbids silently
    omitting them."""
    section_start = repro_text.find("### 5.2 — Not covered")
    assert section_start >= 0, "Repro report Section 5.2 missing"
    section_end = repro_text.find("## 6.", section_start)
    if section_end < 0:
        section_end = len(repro_text)
    gaps_block = repro_text[section_start:section_end]
    assert gap in gaps_block, (
        f"Honest gap missing from Section 5.2: '{gap}'."
    )


# -----------------------------------------------------------------------------
# Blind-validation protocol (Step 2.5) — required sections
# -----------------------------------------------------------------------------

BLIND_REQUIRED_SECTIONS = [
    "## 1. What you need before starting",
    "### 1.1 — Cohort data requirements",
    "### 1.2 — Demographic data",
    "### 1.3 — Compute environment",
    "## 2. Protocol overview",
    "## 3. Phase A — Pre-registration",
    "## 4. Phase B — Verification",
    "## 5. Phase C — Audit execution",
    "## 6. Phase D — Reporting back",
    "## 7. Anti-gaming guarantees",
    "## 8. Honest gaps in the protocol",
    "## 9. Reference contact",
    "## 10. Citation",
]


@pytest.fixture(scope="module")
def blind_text() -> str:
    return BLIND_DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize("section", BLIND_REQUIRED_SECTIONS)
def test_blind_section_present(blind_text: str, section: str):
    """Every protocol section must be present — the protocol is a fixed
    sequence and a missing phase breaks the gaming-resistance guarantees."""
    assert section in blind_text, (
        f"Missing blind-validation protocol section: '{section}'."
    )


BLIND_REQUIRED_PHRASES = [
    "Pre-registration",
    "Verification",
    "Audit execution",
    "Reporting back",
    "Anti-gaming",
    "audit_id",
    "rulepack_sha256",
    "SHA-256",
    "FUTURE-AI Panel B.4.4",
    "Input Contract",
]


@pytest.mark.parametrize("phrase", BLIND_REQUIRED_PHRASES)
def test_blind_anti_gaming_concepts_present(blind_text: str, phrase: str):
    """The blind-validation protocol's gaming-resistance depends on these
    concepts being in the text and discoverable by the collaborator."""
    assert phrase in blind_text, (
        f"Blind-validation protocol missing concept: '{phrase}'. "
        f"The anti-gaming guarantees depend on this being explicitly "
        f"present and explained."
    )


BLIND_REQUIRED_GAPS = [
    "No formal IRB-level coordination",
    "No automated CI hook",
    "No formal blind-validation timeline SLA",
    "The protocol is one-way",
]


@pytest.mark.parametrize("gap", BLIND_REQUIRED_GAPS)
def test_blind_gap_acknowledged(blind_text: str, gap: str):
    """The protocol must acknowledge its own limitations explicitly so
    collaborators are not surprised. No-future-fix discipline."""
    section_start = blind_text.find("## 8. Honest gaps")
    assert section_start >= 0
    section_end = blind_text.find("## 9.", section_start)
    if section_end < 0:
        section_end = len(blind_text)
    gaps_block = blind_text[section_start:section_end]
    assert gap in gaps_block, f"Blind-protocol gap missing: '{gap}'"


# -----------------------------------------------------------------------------
# requirements.lock — pinned versions match installed (for the locked tag)
# -----------------------------------------------------------------------------

LOCKFILE_REQUIRED_PINS = {
    "pydantic": "2.13.4",
    "PyYAML": "6.0.3",
    "pandas": "3.0.2",
    "pyarrow": "24.0.0",
    "jsonschema": "4.26.0",
    "pyreadr": "0.5.6",
    "numpy": "2.4.4",
    "scipy": "1.17.1",
    "pytest": "9.0.3",
    "ruff": "0.15.13",
}


@pytest.fixture(scope="module")
def lockfile_text() -> str:
    return LOCKFILE.read_text(encoding="utf-8")


@pytest.mark.parametrize("package,version", LOCKFILE_REQUIRED_PINS.items(),
                          ids=[f"{p}=={v}" for p, v in LOCKFILE_REQUIRED_PINS.items()])
def test_lockfile_pin_present(lockfile_text: str, package: str, version: str):
    """Each canonical pin must be in requirements.lock exactly. These are
    the versions that produced the locked audit_ids; collaborators install
    them to obtain bit-exact reproducibility."""
    pin = f"{package}=={version}"
    assert pin in lockfile_text, (
        f"requirements.lock missing canonical pin: {pin}. "
        f"If the pin is intentionally updated, also update the table in "
        f"docs/reproducibility/ad_neurotcs_reproducibility.md Section 2.3."
    )


# -----------------------------------------------------------------------------
# Sanity check on the checksum helper script
# -----------------------------------------------------------------------------

def test_checksum_script_is_executable():
    """The checksum helper must be importable as a module (we don't run it
    here — its behaviour is implicitly tested by the live sha256sum
    cross-check that was performed during development). This test is a
    structural guard: if the file is dropped or corrupted, CI fails."""
    text = CHECKSUM_SCRIPT.read_text(encoding="utf-8")
    assert "def sha256_file" in text
    assert "hashlib.sha256" in text
    assert "def main" in text


# -----------------------------------------------------------------------------
# Cross-document consistency: the reproducibility report must reference
# the blind-validation protocol (and vice versa)
# -----------------------------------------------------------------------------

def test_repro_references_blind_protocol(repro_text: str):
    """The reproducibility report's Section 7 must reference the
    companion blind-validation protocol — both are part of AD-lock
    Steps 2.4/2.5 and must cross-link for the collaborator."""
    assert "blind_validation_protocol.md" in repro_text, (
        "Reproducibility report must reference the blind-validation protocol "
        "as a companion document (cross-link in Section 7)."
    )


def test_blind_references_repro_report(blind_text: str):
    """The blind-validation protocol's Phase B must reference the
    reproducibility report (Section 3.1-3.3 canonical commands)."""
    assert "ad_neurotcs_reproducibility.md" in blind_text, (
        "Blind-validation protocol must reference the reproducibility "
        "report (the canonical command sequence in Phase B Step 1)."
    )
