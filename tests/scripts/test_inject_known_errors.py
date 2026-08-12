"""Acceptance tests for scripts/inject_known_errors.py (TDD; external expert
review 2026-08).

Reviewer ask: "deliberately introduce known errors into otherwise valid
longitudinal data and see how reliably the system detects them."

The injector must be:
  - deterministic (same input + same seed => byte-identical outputs; no
    wall-clock, no unseeded randomness),
  - honest (answer key records every mutated cell: subject, row, column,
    original value, injected value, error type),
  - fail-closed (refuses to inject fewer errors than requested unless
    --allow-partial is passed).

The acceptance criterion mirrors the benchmark discipline: on a clean
progressive cohort the audit reports zero impossible/implausible flags; after
injection, every injected subject is flagged and every untouched subject
remains unflagged (zero false positives).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Add scripts/ to sys.path so we can import the injector module
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import inject_known_errors  # noqa: E402

from neurotcs import build_bundle, run_full_audit  # noqa: E402


def _clean_cohort() -> pd.DataFrame:
    """24 subjects with strictly guideline-conformant trajectories.

    Monotone CN -> MCI -> AD progressions (plus stable subjects), 6-month
    visit spacing, no reversions, no short-interval CN->AD jumps: the audit
    must report zero impossible and zero implausible flags on this frame.
    """
    rows = []
    dates = pd.to_datetime(
        ["2019-01-01", "2019-07-01", "2020-01-01", "2020-07-01"]
    )
    trajectories = {
        # 8 progressors reaching AD (injectable sites: AD followed by a visit)
        **{f"PROG{i}": ["CN", "MCI", "AD", "AD"] for i in range(8)},
        # 8 mid-progressors (no AD-then-later-visit site for the default
        # error type except the AD,AD tail above)
        **{f"MCIP{i}": ["CN", "CN", "MCI", "MCI"] for i in range(8)},
        # 8 stable-normal subjects
        **{f"STAB{i}": ["CN", "CN", "CN", "CN"] for i in range(8)},
    }
    for sid, states in trajectories.items():
        for v, (d, s) in enumerate(zip(dates, states)):
            rows.append(
                {"subject_id": sid, "visit": v, "visit_date": d, "state": s}
            )
    return pd.DataFrame(rows)


def _flagged_subjects(df: pd.DataFrame) -> dict[str, list[str]]:
    """Run the real audit and return subjects per severity tier."""
    bundle = build_bundle(run_full_audit({"clinical": df}))
    flags = bundle["neurotcs_bundle"]["deterministic_core"].get("flags", {})
    return {
        tier: sorted(
            {f.get("subject_id") for f in flags.get(tier, [])
             if f.get("subject_id")}
        )
        for tier in ("impossible", "implausible", "informational")
    }


def _run_injector(tmp_path: Path, df: pd.DataFrame, *, n: int, seed: int,
                  extra: list[str] | None = None) -> tuple[Path, Path, int]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    src = tmp_path / f"clean_{seed}_{n}.csv"
    out_dir = tmp_path / f"out_{seed}_{n}"
    df.to_csv(src, index=False)
    rc = inject_known_errors.main([
        "--input", str(src),
        "--out-dir", str(out_dir),
        "--subject-col", "subject_id",
        "--state-col", "state",
        "--states", "CN,MCI,AD",
        "--n-errors", str(n),
        "--seed", str(seed),
        *(extra or []),
    ])
    return out_dir / "injected.csv", out_dir / "answer_key.csv", rc


def test_clean_cohort_is_clean():
    """Precondition: the fixture cohort audits clean (no false positives on
    valid data). If this fails the acceptance test below proves nothing."""
    tiers = _flagged_subjects(_clean_cohort())
    assert tiers["impossible"] == []
    assert tiers["implausible"] == []


def test_injected_errors_are_detected_with_zero_false_positives(tmp_path):
    clean = _clean_cohort()
    injected_csv, key_csv, rc = _run_injector(tmp_path, clean, n=4, seed=7)
    assert rc == 0
    assert injected_csv.exists() and key_csv.exists()

    key = pd.read_csv(key_csv)
    assert len(key) == 4
    assert set(key.columns) >= {
        "subject_id", "row_index", "column", "original_value",
        "injected_value", "error_type",
    }

    injected = pd.read_csv(injected_csv, parse_dates=["visit_date"])
    # exactly the keyed cells differ from the clean frame
    diff_mask = injected["state"].ne(clean["state"])
    assert int(diff_mask.sum()) == 4
    assert sorted(injected.index[diff_mask]) == sorted(key["row_index"])

    tiers = _flagged_subjects(injected)
    flagged = set(tiers["impossible"]) | set(tiers["implausible"])
    injected_subjects = set(key["subject_id"])
    # every injected subject detected...
    assert injected_subjects <= flagged, (
        f"missed: {injected_subjects - flagged}"
    )
    # ...and nobody else flagged (zero false positives)
    assert flagged <= injected_subjects, (
        f"false positives: {flagged - injected_subjects}"
    )


def test_injection_is_deterministic(tmp_path):
    clean = _clean_cohort()
    a_csv, a_key, rc_a = _run_injector(tmp_path / "a", clean, n=4, seed=7)
    b_csv, b_key, rc_b = _run_injector(tmp_path / "b", clean, n=4, seed=7)
    assert rc_a == rc_b == 0
    assert a_csv.read_bytes() == b_csv.read_bytes()
    assert a_key.read_bytes() == b_key.read_bytes()

    c_csv, c_key, rc_c = _run_injector(tmp_path / "c", clean, n=4, seed=8)
    assert rc_c == 0
    assert c_key.read_bytes() != a_key.read_bytes(), (
        "different seed must select a different injection plan on a cohort "
        "with 8 injectable subjects choose 4"
    )


def test_fail_closed_when_not_enough_injectable_sites(tmp_path):
    clean = _clean_cohort()
    # only 8 subjects have an AD visit followed by a later visit
    _, _, rc = _run_injector(tmp_path, clean, n=99, seed=7)
    assert rc != 0

    # --allow-partial downgrades to injecting what exists
    injected_csv, key_csv, rc = _run_injector(
        tmp_path / "partial", clean, n=99, seed=7,
        extra=["--allow-partial"],
    )
    assert rc == 0
    key = pd.read_csv(key_csv)
    assert 0 < len(key) <= 99


def test_manifest_is_deterministic_and_complete(tmp_path):
    clean = _clean_cohort()
    injected_csv, key_csv, rc = _run_injector(tmp_path, clean, n=3, seed=11)
    assert rc == 0
    import json
    manifest = json.loads(
        (injected_csv.parent / "injection_manifest.json").read_text()
    )
    for field in ("seed", "n_requested", "n_injected", "input_sha256",
                  "injected_sha256", "error_type", "tool_version"):
        assert field in manifest, f"manifest missing {field}"
    assert manifest["seed"] == 11
    assert manifest["n_injected"] == 3
    # no wall-clock fields: the manifest must be reproducible byte-for-byte
    assert "timestamp" not in manifest and "created_at" not in manifest
