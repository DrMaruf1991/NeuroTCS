"""Acceptance tests for scripts/sample_flags_for_adjudication.py (TDD;
external expert review 2026-08).

Reviewer ask: "take a representative sample of the flagged transitions from
each dataset and manually review them" — this tool draws the Arm A
adjudication sample specified by docs/VALIDATION_PROTOCOL.md:

  §3  Arm A: sample of flagged AND unflagged records.
  §5  Blinding: reviewers must NOT see severity, rule identity, citations, or
      whether a record was flagged; record order randomized; flagged and
      unflagged interleaved.
  §4  Rubric: each record gets one of DATA_ERROR / CORRECT_RARE /
      CORRECT_COMMON / INDETERMINATE.
  §7  Sample size: n targets from the precision table (configurable here).

The tool must be deterministic (seeded), fail-closed, and must keep the
unblinding key in a separate file the coordinator withholds from reviewers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import sample_flags_for_adjudication  # noqa: E402

# Columns a reviewer must NEVER see (protocol §5 blinding).
_FORBIDDEN_IN_WORKSHEET = {
    "severity", "rule_id", "citation", "details", "flagged", "layer",
}

_RUBRIC = "DATA_ERROR / CORRECT_RARE / CORRECT_COMMON / INDETERMINATE"


def _flags_csv(tmp_path: Path) -> Path:
    """Mimic flags_to_csv output: 12 impossible + 6 implausible flags."""
    rows = []
    for i in range(12):
        rows.append({
            "severity": "impossible", "layer": "staging_clinical",
            "subject_id": f"IMP{i}", "visit": 2, "field": "state",
            "observed_value": "CN", "rule_id": "ad/niaaa_2018",
            "citation": "PMID 29653606", "details": "{}",
        })
    for i in range(6):
        rows.append({
            "severity": "implausible", "layer": "staging_clinical",
            "subject_id": f"PLA{i}", "visit": 1, "field": "state",
            "observed_value": "AD", "rule_id": "ad/niaaa_2018",
            "citation": "PMID 29653606", "details": "{}",
        })
    p = tmp_path / "flags.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def _cohort_csv(tmp_path: Path) -> Path:
    """Cohort long-format frame containing flagged + unflagged subjects."""
    rows = []
    subjects = [f"IMP{i}" for i in range(12)] + [f"PLA{i}" for i in range(6)]
    subjects += [f"OK{i}" for i in range(30)]
    for sid in subjects:
        for v in range(3):
            rows.append({
                "subject_id": sid, "visit": v,
                "visit_date": f"20{20 + v}-01-01", "state": "CN",
            })
    p = tmp_path / "cohort.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def _run(tmp_path: Path, *, n_flagged: int, n_unflagged: int, seed: int,
         extra: list[str] | None = None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / f"out_{seed}_{n_flagged}_{n_unflagged}"
    rc = sample_flags_for_adjudication.main([
        "--flags", str(_flags_csv(tmp_path)),
        "--cohort", str(_cohort_csv(tmp_path)),
        "--subject-col", "subject_id",
        "--n-flagged", str(n_flagged),
        "--n-unflagged", str(n_unflagged),
        "--seed", str(seed),
        "--out-dir", str(out_dir),
        *(extra or []),
    ])
    return out_dir, rc


def test_worksheet_is_blinded_and_interleaved(tmp_path):
    out_dir, rc = _run(tmp_path, n_flagged=9, n_unflagged=6, seed=42)
    assert rc == 0
    ws = pd.read_csv(out_dir / "adjudication_worksheet.csv")

    # protocol §5: nothing that reveals flag status or rule identity
    assert not (_FORBIDDEN_IN_WORKSHEET & set(ws.columns)), (
        f"blinding leak: {sorted(_FORBIDDEN_IN_WORKSHEET & set(ws.columns))}"
    )
    # 9 flagged + 6 unflagged records, blinded record ids
    assert len(ws) == 15
    assert ws["record_id"].is_unique
    # record ids are assigned AFTER the shuffle, so presentation order can
    # never be reverse-engineered into flag status
    assert list(ws["record_id"]) == sorted(ws["record_id"], key=lambda r: int(r[1:]))
    # adjudication columns present and empty, rubric documented
    for col in ("adjudicated_label", "reviewer_id", "comments"):
        assert col in ws.columns
    assert ws["adjudicated_label"].isna().all()


def test_stratification_and_key_completeness(tmp_path):
    out_dir, rc = _run(tmp_path, n_flagged=9, n_unflagged=6, seed=42)
    assert rc == 0
    key = pd.read_csv(out_dir / "unblinding_key.csv")
    ws = pd.read_csv(out_dir / "adjudication_worksheet.csv")

    assert set(key["record_id"]) == set(ws["record_id"])
    flagged_key = key[key["flagged"]]
    # proportional stratification over severity tiers: 12 impossible vs 6
    # implausible flags -> a 9-record sample takes 6 and 3
    counts = flagged_key["severity"].value_counts().to_dict()
    assert counts == {"impossible": 6, "implausible": 3}
    # unflagged sampled from subjects with no flag at all
    unflagged_subjects = set(key.loc[~key["flagged"], "subject_id"])
    assert all(s.startswith("OK") for s in unflagged_subjects)
    assert len(unflagged_subjects) == 6


def test_deterministic_and_seed_sensitive(tmp_path):
    a, rc_a = _run(tmp_path / "a", n_flagged=9, n_unflagged=6, seed=42)
    b, rc_b = _run(tmp_path / "b", n_flagged=9, n_unflagged=6, seed=42)
    c, rc_c = _run(tmp_path / "c", n_flagged=9, n_unflagged=6, seed=43)
    assert rc_a == rc_b == rc_c == 0
    for fname in ("adjudication_worksheet.csv", "unblinding_key.csv"):
        assert (a / fname).read_bytes() == (b / fname).read_bytes()
    assert (
        (a / "unblinding_key.csv").read_bytes()
        != (c / "unblinding_key.csv").read_bytes()
    )


def test_fail_closed_on_oversized_request(tmp_path):
    _, rc = _run(tmp_path, n_flagged=999, n_unflagged=6, seed=42)
    assert rc != 0
    out_dir, rc = _run(
        tmp_path / "partial", n_flagged=999, n_unflagged=6, seed=42,
        extra=["--allow-partial"],
    )
    assert rc == 0
    key = pd.read_csv(out_dir / "unblinding_key.csv")
    assert int(key["flagged"].sum()) == 18  # every available flag sampled


def test_manifest_reproducible_and_rubric_documented(tmp_path):
    out_dir, rc = _run(tmp_path, n_flagged=9, n_unflagged=6, seed=42)
    assert rc == 0
    manifest = json.loads((out_dir / "sampling_manifest.json").read_text())
    for field in ("seed", "n_flagged_requested", "n_flagged_sampled",
                  "n_unflagged_sampled", "flags_sha256", "cohort_sha256",
                  "protocol", "rubric"):
        assert field in manifest, f"manifest missing {field}"
    assert "timestamp" not in manifest and "created_at" not in manifest
    assert _RUBRIC in manifest["rubric"]
    assert "VALIDATION_PROTOCOL" in manifest["protocol"]
