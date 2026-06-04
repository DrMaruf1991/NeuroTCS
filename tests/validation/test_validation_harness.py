"""Tests for the Arm B error-injection validation harness.

These prove the apparatus is correct on synthetic inputs:
  - the statistical interval functions match known reference values and respect
    boundary/degenerate cases;
  - the scorer joins injected coordinates to flags correctly, including the
    sheet-prefix and visit-type tolerance;
  - the injector is deterministic for a fixed (cohort, spec, seed), never
    mutates the input, and records a complete ground-truth manifest.

The injector/end-to-end tests build a tiny synthetic workbook in a temp dir, so
they need no external or DUA-gated data.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from neurotcs.validation import (
    ErrorType,
    InjectionSpec,
    clopper_pearson_interval,
    inject_errors,
    score_detection,
    wilson_interval,
)
from neurotcs.validation.scorer import _flag_keys
from neurotcs.validation.taxonomy import InjectedError, InjectionManifest


# --------------------------------------------------------------------------- #
# Statistical interval correctness
# --------------------------------------------------------------------------- #
def test_wilson_matches_reference():
    lo, hi = wilson_interval(8, 10)
    assert lo == pytest.approx(0.490, abs=2e-3)
    assert hi == pytest.approx(0.943, abs=2e-3)


def test_wilson_half_proportion_symmetric():
    lo, hi = wilson_interval(5, 10)
    # symmetric around 0.5
    assert (lo + hi) == pytest.approx(1.0, abs=1e-9)


def test_wilson_zero_n_is_uninformative():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_rejects_bad_counts():
    with pytest.raises(ValueError):
        wilson_interval(5, 3)


def test_clopper_pearson_zero_successes():
    lo, hi = clopper_pearson_interval(0, 10)
    assert lo == 0.0
    assert hi == pytest.approx(0.3085, abs=1e-3)


def test_clopper_pearson_all_successes():
    lo, hi = clopper_pearson_interval(10, 10)
    assert lo == pytest.approx(0.6915, abs=1e-3)
    assert hi == 1.0


def test_clopper_pearson_interior():
    lo, hi = clopper_pearson_interval(2, 20)
    assert lo == pytest.approx(0.0123, abs=2e-3)
    assert hi == pytest.approx(0.3170, abs=2e-3)


def test_clopper_pearson_zero_n():
    assert clopper_pearson_interval(0, 0) == (0.0, 1.0)


# --------------------------------------------------------------------------- #
# Scorer correctness (pure, synthetic)
# --------------------------------------------------------------------------- #
def _mk_manifest(injected, clean):
    m = InjectionManifest()
    m.injected = injected
    m.clean_keys = set(clean)
    return m


def test_scorer_detects_exact_coordinate():
    inj = [
        InjectedError("P1", "plasma_nfl_pgml", "0", ErrorType.UNIT_ERROR,
                      1.0, 1000.0, "FL"),
    ]
    manifest = _mk_manifest(inj, clean=set())
    flags = {"impossible": [
        {"subject_id": "P1", "field": "plasma_nfl_pgml", "visit": "0"},
    ]}
    rep = score_detection(manifest, flags)
    assert rep.total_detected == 1
    assert rep.overall_coverage == 1.0


def test_scorer_misses_unflagged_coordinate():
    inj = [
        InjectedError("P1", "plasma_nfl_pgml", "0", ErrorType.SIGN_FLIP,
                      1.0, -2.0, "FL"),
    ]
    manifest = _mk_manifest(inj, clean=set())
    flags = {"impossible": [
        {"subject_id": "P2", "field": "plasma_nfl_pgml", "visit": "0"},
    ]}
    rep = score_detection(manifest, flags)
    assert rep.total_detected == 0
    assert rep.overall_coverage == 0.0


def test_scorer_handles_sheet_prefixed_field():
    inj = [
        InjectedError("P1", "apoe_genotype", None,
                      ErrorType.CATEGORICAL_INVALID, "e3/e3", "e3/e5", "EN"),
    ]
    manifest = _mk_manifest(inj, clean=set())
    # NeuroTCS emits the field as 'EN:apoe_genotype'
    flags = {"impossible": [
        {"subject_id": "P1", "field": "EN:apoe_genotype", "visit": None},
    ]}
    rep = score_detection(manifest, flags)
    assert rep.total_detected == 1


def test_scorer_counts_false_positive_on_clean_coordinate():
    manifest = _mk_manifest(
        injected=[],
        clean={("P9", "plasma_nfl_pgml", "0")},
    )
    flags = {"implausible": [
        {"subject_id": "P9", "field": "plasma_nfl_pgml", "visit": "0"},
    ]}
    rep = score_detection(manifest, flags)
    assert rep.false_positives_on_clean == 1
    assert rep.clean_coordinates == 1
    assert rep.specificity == 0.0


def test_scorer_per_type_breakdown():
    inj = [
        InjectedError("P1", "f", "0", ErrorType.UNIT_ERROR, 1, 2, "FL"),
        InjectedError("P2", "f", "0", ErrorType.UNIT_ERROR, 1, 2, "FL"),
        InjectedError("P3", "f", "0", ErrorType.SIGN_FLIP, 1, -1, "FL"),
    ]
    manifest = _mk_manifest(inj, clean=set())
    flags = {"impossible": [
        {"subject_id": "P1", "field": "f", "visit": "0"},
        {"subject_id": "P3", "field": "f", "visit": "0"},
    ]}
    rep = score_detection(manifest, flags)
    by = {str(r.error_type): r for r in rep.per_type}
    assert by["unit_error"].detected == 1
    assert by["unit_error"].injected == 2
    assert by["sign_flip"].detected == 1
    assert by["sign_flip"].injected == 1


def test_report_to_dict_carries_honest_note():
    manifest = _mk_manifest([], set())
    rep = score_detection(manifest, {})
    d = rep.to_dict()
    assert "_honest_note" in d
    assert "not accuracy" in d["_honest_note"].lower()


def test_flag_keys_extracts_all_tiers():
    flags = {
        "impossible": [{"subject_id": "A", "field": "x", "visit": "0"}],
        "implausible": [{"subject_id": "B", "field": "y", "visit": "1"}],
        "informational": [{"subject_id": "C", "field": "z", "visit": None}],
    }
    keys = _flag_keys(flags)
    assert ("A", "x", "0") in keys
    assert ("B", "y", "1") in keys
    assert ("C", "z", None) in keys


# --------------------------------------------------------------------------- #
# Injector correctness on a synthetic workbook (no external data)
# --------------------------------------------------------------------------- #
def _write_synthetic_cohort(path: Path) -> None:
    en = pd.DataFrame({
        "subject_id": [f"S{i:03d}" for i in range(1, 11)],
        "apoe_genotype": ["e3/e3"] * 10,
    })
    rows = []
    for i in range(1, 11):
        for v in (0, 1):
            rows.append({
                "subject_id": f"S{i:03d}",
                "visit": v,
                "plasma_nfl_pgml": 50.0 + i,
                "plasma_ptau217_pgml": 0.4 + i / 100,
            })
    fl = pd.DataFrame(rows)
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        en.to_excel(w, sheet_name="EN", index=False)
        fl.to_excel(w, sheet_name="FL", index=False)


def test_injector_is_deterministic(tmp_path):
    src = tmp_path / "clean.xlsx"
    _write_synthetic_cohort(src)
    spec = InjectionSpec(counts={
        ErrorType.UNIT_ERROR: 3,
        ErrorType.SIGN_FLIP: 2,
        ErrorType.CATEGORICAL_INVALID: 2,
    })
    m1 = inject_errors(src, spec, seed=7, out_path=tmp_path / "c1.xlsx")
    m2 = inject_errors(src, spec, seed=7, out_path=tmp_path / "c2.xlsx")
    assert m1.injected_keys() == m2.injected_keys()
    assert {e.error_type for e in m1.injected} == {e.error_type for e in m2.injected}


def test_injector_does_not_mutate_input(tmp_path):
    src = tmp_path / "clean.xlsx"
    _write_synthetic_cohort(src)
    before = pd.read_excel(src, sheet_name="FL")
    spec = InjectionSpec(counts={ErrorType.UNIT_ERROR: 5})
    inject_errors(src, spec, seed=1, out_path=tmp_path / "out.xlsx")
    after = pd.read_excel(src, sheet_name="FL")
    pd.testing.assert_frame_equal(before, after)


def test_injector_records_complete_manifest(tmp_path):
    src = tmp_path / "clean.xlsx"
    _write_synthetic_cohort(src)
    spec = InjectionSpec(counts={
        ErrorType.UNIT_ERROR: 3,
        ErrorType.IMPLAUSIBLE_HIGH: 2,
        ErrorType.CATEGORICAL_INVALID: 2,
    })
    m = inject_errors(src, spec, seed=3, out_path=tmp_path / "out.xlsx")
    assert len(m.injected) == 7
    # every injected error carries a valid coordinate
    for e in m.injected:
        assert e.subject_id.startswith("S")
        assert e.field
    # clean keys are disjoint from injected coordinates
    assert not (m.injected_keys() & m.clean_keys)


def test_injector_corrupts_the_output_values(tmp_path):
    src = tmp_path / "clean.xlsx"
    _write_synthetic_cohort(src)
    spec = InjectionSpec(counts={ErrorType.UNIT_ERROR: 4})
    m = inject_errors(src, spec, seed=5, out_path=tmp_path / "out.xlsx")
    out = pd.read_excel(tmp_path / "out.xlsx", sheet_name="FL")
    # at least one injected coordinate now holds the unit-scaled value
    changed = 0
    for e in m.injected:
        mask = (out["subject_id"] == e.subject_id) & (out["visit"].astype(str) == e.visit)
        if mask.any():
            val = out.loc[mask, e.field].iloc[0]
            if math.isclose(float(val), float(e.corrupted_value), rel_tol=1e-6):
                changed += 1
    assert changed == 4


def test_injector_raises_when_pool_exhausted(tmp_path):
    src = tmp_path / "clean.xlsx"
    _write_synthetic_cohort(src)
    # request more numeric errors than injectable cells (10 subj x 2 visits x 2
    # fields = 40 numeric cells)
    spec = InjectionSpec(counts={ErrorType.UNIT_ERROR: 41})
    with pytest.raises(ValueError):
        inject_errors(src, spec, seed=1, out_path=tmp_path / "out.xlsx")
