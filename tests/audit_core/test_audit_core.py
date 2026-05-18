"""
Tests for neurotcs.audit_core (Piece 4 of 7).

Coverage:
  - Trajectory construction and invariants (8 tests)
  - cTCS / pTCS / uTCS correctness on synthetic data (10 tests)
  - Generator-matrix construction from rule pack priors (4 tests)
  - Cluster bootstrap + BCa + Huber (8 tests)
  - End-to-end audit pipeline (6 tests)
  - Real ADNI re-validation (1 test)
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from neurotcs import load_rulepack
from neurotcs.audit_core import (
    Trajectory,
    audit,
    build_generator,
    cluster_bootstrap,
    ctcs_per_patient,
    huber_m_estimate,
    paired_cluster_bootstrap_difference,
    ptcs_per_patient,
    score_cohort,
    trajectories_from_dataframe,
    utcs_per_patient,
)

PASS = "\033[32m\u2713\033[0m"
FAIL = "\033[31m\u2717\033[0m"


# ============================================================
# Helpers
# ============================================================

def _make_traj(patient_id: str, states: list[str],
                intervals_days: list[int],
                start: date = date(2020, 1, 1),
                probs: list[list[float]] | None = None,
                labels: tuple[str, ...] | None = None) -> Trajectory:
    """Build a Trajectory with explicit intervals."""
    dates = [start]
    for d in intervals_days:
        dates.append(dates[-1] + timedelta(days=d))
    p_arr = np.asarray(probs) if probs is not None else None
    return Trajectory(
        patient_id=patient_id,
        states=tuple(states),
        dates=tuple(dates),
        probabilities=p_arr,
        state_labels=labels,
    )


# ============================================================
# Trajectory tests
# ============================================================

def test_trajectory_length_and_transitions():
    t = _make_traj("p1", ["CN", "MCI", "AD"], [365, 365])
    assert t.length == 3
    assert t.num_transitions == 2
    print(f"  {PASS} test_trajectory_length_and_transitions")


def test_trajectory_zero_length_ok():
    t = Trajectory(patient_id="p0", states=(), dates=())
    assert t.length == 0
    assert t.num_transitions == 0
    print(f"  {PASS} test_trajectory_zero_length_ok")


def test_trajectory_single_visit_ok():
    t = _make_traj("p1", ["CN"], [])
    assert t.length == 1
    assert t.num_transitions == 0
    print(f"  {PASS} test_trajectory_single_visit_ok")


def test_trajectory_mismatched_lengths_fail():
    try:
        Trajectory(patient_id="p1", states=("CN", "MCI"), dates=(date(2020, 1, 1),))
        assert False, "should fail mismatched lengths"
    except ValueError:
        pass
    print(f"  {PASS} test_trajectory_mismatched_lengths_fail")


def test_trajectory_descending_dates_fail():
    try:
        Trajectory(
            patient_id="p1", states=("CN", "MCI"),
            dates=(date(2021, 1, 1), date(2020, 1, 1)),
        )
        assert False
    except ValueError:
        pass
    print(f"  {PASS} test_trajectory_descending_dates_fail")


def test_trajectory_with_probabilities():
    t = _make_traj(
        "p1", ["CN", "MCI"], [365],
        probs=[[0.8, 0.15, 0.05], [0.2, 0.7, 0.1]],
        labels=("p_CN", "p_MCI", "p_AD"),
    )
    confs = t.transition_confidences()
    assert len(confs) == 1
    assert abs(confs[0][0] - 0.8) < 1e-9 and abs(confs[0][1] - 0.7) < 1e-9
    print(f"  {PASS} test_trajectory_with_probabilities")


def test_trajectory_probabilities_out_of_range_fail():
    try:
        _make_traj(
            "p1", ["CN", "MCI"], [365],
            probs=[[1.2, 0.0, 0.0], [0.5, 0.5, 0.0]],  # 1.2 invalid
            labels=("p_CN", "p_MCI", "p_AD"),
        )
        assert False
    except ValueError:
        pass
    print(f"  {PASS} test_trajectory_probabilities_out_of_range_fail")


def test_trajectories_from_dataframe():
    df = pd.DataFrame({
        "RID": [1, 1, 1, 2, 2],
        "EXAMDATE": ["2020-01-01", "2021-01-01", "2022-01-01",
                      "2020-06-01", "2021-06-01"],
        "DIAGNOSIS": ["CN", "MCI", "AD", "CN", "MCI"],
    })
    trajectories = trajectories_from_dataframe(
        df,
        patient_id_col="RID",
        visit_date_col="EXAMDATE",
        state_col="DIAGNOSIS",
    )
    assert len(trajectories) == 2
    assert trajectories[0].num_transitions == 2
    assert trajectories[1].num_transitions == 1
    print(f"  {PASS} test_trajectories_from_dataframe")


# ============================================================
# cTCS / pTCS / uTCS scoring tests
# ============================================================

def test_ctcs_perfect_trajectory():
    """A perfectly-admissible AD trajectory → cTCS = 1.0."""
    pack = load_rulepack("ad/niaaa_2018")
    t = _make_traj("p1", ["CN", "MCI", "AD"], [400, 400])
    score = ctcs_per_patient(t, pack)
    assert abs(score - 1.0) < 1e-9, f"expected 1.0, got {score}"
    print(f"  {PASS} test_ctcs_perfect_trajectory")


def test_ctcs_all_bad_trajectory():
    """All-inadmissible: AD->CN inadmissible, CN->AD over 100d (<365 min)."""
    pack = load_rulepack("ad/niaaa_2018")
    t = _make_traj("p1", ["AD", "CN", "AD"], [100, 100])
    score = ctcs_per_patient(t, pack)
    assert score == 0.0, f"expected 0.0, got {score}"
    print(f"  {PASS} test_ctcs_all_bad_trajectory")


def test_ctcs_mixed_trajectory():
    """One admissible (CN->MCI), one not (MCI->CN at 100d < 180d min) → 0.5."""
    pack = load_rulepack("ad/niaaa_2018")
    t = _make_traj("p1", ["CN", "MCI", "CN"], [400, 100])  # 100d < 180d min
    score = ctcs_per_patient(t, pack)
    assert abs(score - 0.5) < 1e-9, f"expected 0.5, got {score}"
    print(f"  {PASS} test_ctcs_mixed_trajectory")


def test_ctcs_self_loop_admissible():
    pack = load_rulepack("ad/niaaa_2018")
    t = _make_traj("p1", ["MCI", "MCI", "MCI"], [365, 365])
    score = ctcs_per_patient(t, pack)
    assert score == 1.0
    print(f"  {PASS} test_ctcs_self_loop_admissible")


def test_ctcs_none_for_single_visit():
    pack = load_rulepack("ad/niaaa_2018")
    t = _make_traj("p1", ["CN"], [])
    assert ctcs_per_patient(t, pack) is None
    print(f"  {PASS} test_ctcs_none_for_single_visit")


def test_build_generator_for_ad_niaaa_2018():
    pack = load_rulepack("ad/niaaa_2018")
    gen = build_generator(pack, prior_type="clinical")
    assert gen is not None
    # State space is CN, MCI, AD
    assert set(gen.state_index.keys()) == {"CN", "MCI", "AD"}
    # Rows sum to ~0
    row_sums = gen.Q.sum(axis=1)
    assert np.allclose(row_sums, 0, atol=1e-12)
    # Off-diagonal >= 0
    Q = gen.Q.copy()
    np.fill_diagonal(Q, 0)
    assert (Q >= 0).all()
    print(f"  {PASS} test_build_generator_for_ad_niaaa_2018 "
          f"(priors_covered={gen.priors_covered})")


def test_build_generator_population_priors():
    pack = load_rulepack("ad/niaaa_2018")
    gen_clinical = build_generator(pack, prior_type="clinical")
    gen_pop = build_generator(pack, prior_type="population")
    assert gen_clinical is not None and gen_pop is not None
    # Population MCI->AD prior (0.06 ACR) differs from clinical (0.11 ACR)
    # Note: pre-v1.5.0 these were 0.27 and 0.415 (cumulative not annual);
    # see ERRATA.md E-2026-001.
    i_mci = gen_clinical.state_index["MCI"]
    i_ad = gen_clinical.state_index["AD"]
    assert not np.isclose(gen_clinical.Q[i_mci, i_ad],
                            gen_pop.Q[i_mci, i_ad])
    print(f"  {PASS} test_build_generator_population_priors")


def test_build_generator_no_priors_returns_none():
    """AA 2024 pack has no priors; generator must be None."""
    pack = load_rulepack("ad/aa_2024")
    gen = build_generator(pack, prior_type="clinical")
    assert gen is None
    print(f"  {PASS} test_build_generator_no_priors_returns_none")


def test_ptcs_admissible_higher_than_inadmissible():
    """pTCS should be higher (less negative) for admissible trajectories."""
    pack = load_rulepack("ad/niaaa_2018")
    gen = build_generator(pack, prior_type="clinical")
    good = _make_traj("g", ["CN", "MCI"], [365])
    bad = _make_traj("b", ["AD", "CN"], [365])  # inadmissible
    p_good = ptcs_per_patient(good, gen)
    p_bad = ptcs_per_patient(bad, gen)
    assert p_good > p_bad, f"good={p_good}, bad={p_bad}"
    print(f"  {PASS} test_ptcs_admissible_higher_than_inadmissible "
          f"(good={p_good:.3f}, bad={p_bad:.3f})")


def test_utcs_with_probabilities():
    """uTCS with high confidence on admissible → high uTCS."""
    pack = load_rulepack("ad/niaaa_2018")
    high_conf = _make_traj(
        "p1", ["CN", "MCI"], [365],
        probs=[[0.9, 0.05, 0.05], [0.1, 0.85, 0.05]],
        labels=("p_CN", "p_MCI", "p_AD"),
    )
    u = utcs_per_patient(high_conf, pack)
    # 0.9 * 0.85 * 1.0 = 0.765
    assert abs(u - 0.9 * 0.85) < 1e-9
    print(f"  {PASS} test_utcs_with_probabilities")


def test_utcs_falls_back_to_ctcs_without_probabilities():
    pack = load_rulepack("ad/niaaa_2018")
    t = _make_traj("p1", ["CN", "MCI"], [365])
    assert utcs_per_patient(t, pack) == ctcs_per_patient(t, pack)
    print(f"  {PASS} test_utcs_falls_back_to_ctcs_without_probabilities")


def test_score_cohort_aligned_arrays():
    pack = load_rulepack("ad/niaaa_2018")
    trajectories = [
        _make_traj("p1", ["CN", "MCI"], [400]),
        _make_traj("p2", ["AD", "CN"], [365]),  # inadmissible
        _make_traj("p3", ["CN"], []),  # zero transitions, skipped
    ]
    scores = score_cohort(trajectories, pack)
    assert len(scores.patients) == 2
    assert scores.ctcs.shape == (2,)
    assert scores.utcs.shape == (2,)
    assert scores.ptcs is not None
    assert scores.ptcs.shape == (2,)
    print(f"  {PASS} test_score_cohort_aligned_arrays")


# ============================================================
# Bootstrap tests
# ============================================================

def test_huber_equals_median_on_skewed_data():
    rng = np.random.default_rng(0)
    # Heavy-tailed: 100 standard normal + 5 outliers
    x = np.concatenate([rng.standard_normal(100), [10, 12, 15, -20, 50]])
    h = huber_m_estimate(x)
    m = float(np.mean(x))
    med = float(np.median(x))
    # Huber should be closer to median than mean is
    assert abs(h - med) < abs(m - med), f"h={h}, mean={m}, median={med}"
    print(f"  {PASS} test_huber_equals_median_on_skewed_data "
          f"(h={h:.3f}, mean={m:.3f}, median={med:.3f})")


def test_huber_equals_mean_on_clean_data():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(1000)
    h = huber_m_estimate(x)
    m = float(np.mean(x))
    assert abs(h - m) < 0.05, f"h={h}, mean={m}"
    print(f"  {PASS} test_huber_equals_mean_on_clean_data")


def test_cluster_bootstrap_deterministic():
    x = np.array([0.9, 0.95, 1.0, 0.8, 0.85, 1.0, 0.9])
    r1 = cluster_bootstrap(x, B=500, seed=42, ci_method="bca")
    r2 = cluster_bootstrap(x, B=500, seed=42, ci_method="bca")
    assert r1.ci_low == r2.ci_low
    assert r1.ci_high == r2.ci_high
    assert r1.point == r2.point
    print(f"  {PASS} test_cluster_bootstrap_deterministic")


def test_cluster_bootstrap_ci_contains_point():
    rng = np.random.default_rng(2)
    x = rng.normal(0.9, 0.05, size=200)
    r = cluster_bootstrap(x, B=1000, seed=42, ci_method="bca")
    assert r.ci_low <= r.point <= r.ci_high
    print(f"  {PASS} test_cluster_bootstrap_ci_contains_point "
          f"({r.ci_low:.4f} <= {r.point:.4f} <= {r.ci_high:.4f})")


def test_cluster_bootstrap_bca_vs_percentile_similar_for_symmetric():
    rng = np.random.default_rng(3)
    x = rng.normal(0.0, 1.0, size=500)
    bca = cluster_bootstrap(x, B=1000, seed=42, ci_method="bca")
    pct = cluster_bootstrap(x, B=1000, seed=42, ci_method="percentile")
    # On symmetric clean data BCa ~ percentile (within 0.05)
    assert abs(bca.ci_low - pct.ci_low) < 0.05
    assert abs(bca.ci_high - pct.ci_high) < 0.05
    print(f"  {PASS} test_cluster_bootstrap_bca_vs_percentile_similar_for_symmetric")


def test_cluster_bootstrap_narrower_ci_with_more_data():
    rng = np.random.default_rng(4)
    small = rng.normal(0.9, 0.05, size=20)
    large = rng.normal(0.9, 0.05, size=2000)
    r_s = cluster_bootstrap(small, B=500, seed=42)
    r_l = cluster_bootstrap(large, B=500, seed=42)
    width_s = r_s.ci_high - r_s.ci_low
    width_l = r_l.ci_high - r_l.ci_low
    assert width_l < width_s, f"width_l={width_l}, width_s={width_s}"
    print(f"  {PASS} test_cluster_bootstrap_narrower_ci_with_more_data")


def test_paired_bootstrap_difference():
    rng = np.random.default_rng(5)
    a = rng.normal(0.92, 0.05, size=200)
    b = a - 0.03 + rng.normal(0, 0.01, size=200)  # b ≈ a - 0.03 (paired)
    diff = paired_cluster_bootstrap_difference(a, b, B=500, seed=42)
    # CI should bracket the true difference of ~0.03
    assert 0.015 < diff.point < 0.045
    print(f"  {PASS} test_paired_bootstrap_difference "
          f"(diff={diff.point:.4f}, CI=[{diff.ci_low:.4f}, {diff.ci_high:.4f}])")


def test_cluster_bootstrap_single_value_degenerate():
    r = cluster_bootstrap(np.array([0.5]), B=100, seed=42)
    assert r.point == 0.5
    assert r.ci_low == 0.5 and r.ci_high == 0.5
    print(f"  {PASS} test_cluster_bootstrap_single_value_degenerate")


# ============================================================
# End-to-end audit pipeline
# ============================================================

def test_audit_end_to_end_synthetic():
    pack = load_rulepack("ad/niaaa_2018")
    # 50 patients with perfect trajectories
    trajectories = []
    for i in range(50):
        trajectories.append(
            _make_traj(f"p{i}", ["CN", "MCI", "AD"], [400, 400])
        )
    result = audit(trajectories, pack, bootstrap_B=200, seed=42)
    assert result.ctcs.available
    assert result.ctcs.ci.point == 1.0
    assert result.ctcs.ci.ci_low == 1.0 and result.ctcs.ci.ci_high == 1.0
    assert result.n_flagged == 0
    print(f"  {PASS} test_audit_end_to_end_synthetic (cTCS=1.0, 0 flags)")


def test_audit_id_deterministic():
    pack = load_rulepack("ad/niaaa_2018")
    trajectories = [
        _make_traj(f"p{i}", ["CN", "MCI"], [365]) for i in range(10)
    ]
    r1 = audit(trajectories, pack, bootstrap_B=100, seed=42)
    r2 = audit(trajectories, pack, bootstrap_B=100, seed=42)
    assert r1.audit_id == r2.audit_id
    print(f"  {PASS} test_audit_id_deterministic ({r1.audit_id[:16]}...)")


def test_audit_id_changes_with_seed():
    pack = load_rulepack("ad/niaaa_2018")
    trajectories = [
        _make_traj(f"p{i}", ["CN", "MCI"], [365]) for i in range(10)
    ]
    r1 = audit(trajectories, pack, bootstrap_B=100, seed=42)
    r2 = audit(trajectories, pack, bootstrap_B=100, seed=43)
    assert r1.audit_id != r2.audit_id
    print(f"  {PASS} test_audit_id_changes_with_seed")


def test_audit_with_probabilities_utcs_differs_from_ctcs():
    pack = load_rulepack("ad/niaaa_2018")
    rng = np.random.default_rng(0)
    trajectories = []
    for i in range(30):
        states = ["CN", "MCI"]
        # Random confidences
        p1 = rng.dirichlet([2, 1, 1])
        p2 = rng.dirichlet([1, 2, 1])
        trajectories.append(_make_traj(
            f"p{i}", states, [365],
            probs=[p1.tolist(), p2.tolist()],
            labels=("p_CN", "p_MCI", "p_AD"),
        ))
    result = audit(trajectories, pack, bootstrap_B=100, seed=42)
    # cTCS == 1 (all admissible), uTCS < 1 (probabilities weight it down)
    assert abs(result.ctcs.ci.point - 1.0) < 1e-9
    assert result.utcs.ci.point < 1.0
    print(f"  {PASS} test_audit_with_probabilities_utcs_differs_from_ctcs "
          f"(cTCS={result.ctcs.ci.point:.4f}, uTCS={result.utcs.ci.point:.4f})")


def test_audit_ptcs_unavailable_on_aa_2024():
    """AA 2024 has no priors; pTCS should report unavailable."""
    pack = load_rulepack("ad/aa_2024")
    trajectories = [
        _make_traj(f"p{i}", ["Stage_1", "Stage_2"], [365]) for i in range(10)
    ]
    result = audit(trajectories, pack, bootstrap_B=100, seed=42)
    assert result.ctcs.available
    assert not result.ptcs.available
    assert "transition_priors" in (result.ptcs.skipped_reason or "")
    print(f"  {PASS} test_audit_ptcs_unavailable_on_aa_2024")


def test_audit_skeleton_rejected():
    """No skeleton packs exist anymore — but a placeholder rule pack should
    fail closed if someone tries to audit with it. Synthesize the negative
    case via a freshly built RulePack with status='skeleton'."""
    from datetime import date as _date

    from neurotcs.rulepack.loader import LoadedRulePack, RulePackLoadError
    from neurotcs.rulepack.schema import (
        Citation,
        DiseaseDomain,
        RulePack,
        RulePackStatus,
        State,
    )
    cit = Citation(citation_pmid="1", citation_text="x")
    rp = RulePack(
        schema_version="1.1.0",
        rulepack_id="test/skel@0.1.0",
        ruleset_version="0.1.0",
        effective_date=_date.today(),
        status=RulePackStatus.SKELETON,
        disease_domain=DiseaseDomain.CUSTOM,
        framework_name="Test",
        transcribed_by="Test",
        clinical_source_authority="Test",
        anchor_citation=cit,
        state_space=[
            State(name="A", description="a", ordinal_rank=0),
            State(name="B", description="b", ordinal_rank=1),
        ],
        admissible_transitions=[],
    )
    loaded = LoadedRulePack(
        rulepack=rp, sha256="0" * 64, source_path="(synthetic)",
        loaded_at_utc="2026-05-17T00:00:00+00:00",
    )
    try:
        audit([], loaded, bootstrap_B=10, seed=42)
        assert False
    except RulePackLoadError as e:
        assert "skeleton" in str(e).lower() or "production" in str(e).lower()
    print(f"  {PASS} test_audit_skeleton_rejected")


# ============================================================
# Real ADNI end-to-end (only if data present)
# ============================================================

def test_real_adni_audit_end_to_end():
    """Real ADNI run: 12,006 transitions, expect 65 flagged (0.54%)."""
    dxsum = Path("/home/claude/adni_work/ADNIMERGE2/data/DXSUM.rda")
    if not dxsum.exists():
        print("  ⏭  test_real_adni_audit_end_to_end (skipped: no ADNI data)")
        return
    import warnings
    warnings.filterwarnings("ignore")
    import pyreadr
    dx = pyreadr.read_r(str(dxsum))["DXSUM"]
    dx = dx[dx["DIAGNOSIS"].isin(["CN", "MCI", "Dementia"])].copy()
    trajectories = trajectories_from_dataframe(
        dx,
        patient_id_col="RID",
        visit_date_col="EXAMDATE",
        state_col="DIAGNOSIS",
        state_label_map={"Dementia": "AD"},
        skip_invalid=True,
    )
    pack = load_rulepack("ad/niaaa_2018")
    result = audit(trajectories, pack, bootstrap_B=500, seed=42)
    # Spec invariant from prior validation
    assert result.n_transitions == 12006, (
        f"expected 12006 transitions, got {result.n_transitions}")
    assert result.n_flagged == 65, (
        f"expected 65 flagged, got {result.n_flagged}")
    # cTCS = 1 - 65/12006 = 0.99459
    expected_ctcs = 1.0 - 65 / 12006
    assert abs(result.ctcs.ci.point - expected_ctcs) < 1e-3
    # pTCS should be available
    assert result.ptcs.available
    print(f"  {PASS} test_real_adni_audit_end_to_end "
          f"(cTCS={result.ctcs.ci.point:.4f}, "
          f"pTCS={result.ptcs.ci.point:.4f}, "
          f"uTCS={result.utcs.ci.point:.4f}, "
          f"n_flagged={result.n_flagged}/{result.n_transitions})")


# ============================================================
# TRAC end-to-end audit tests (schema v1.2 conditional admissibility)
# ============================================================

def _make_trac_trajectory(
    states: list[str],
    treatment_status: list[str],
    interval_days: int = 365,
    patient_id: str = "TEST_TRAC_001",
) -> Trajectory:
    """Build a synthetic trajectory carrying treatment_status per visit."""
    base = date(2025, 1, 1)
    dates = tuple(base + timedelta(days=i * interval_days)
                   for i in range(len(states)))
    return Trajectory(
        patient_id=patient_id,
        dates=dates,
        states=tuple(states),
        treatment_status=tuple(treatment_status),
    )


def test_trac_treated_patient_scores_perfect():
    """Treated A+ -> Full_TRAC trajectory should score cTCS = 1.0."""
    pack = load_rulepack("ad/aa_2024_trac")
    traj = _make_trac_trajectory(
        states=["A_pos", "Partial_TRAC", "Full_TRAC"],
        treatment_status=["anti_amyloid_active",
                           "anti_amyloid_active",
                           "anti_amyloid_active"],
    )
    score = ctcs_per_patient(traj, pack)
    assert score == 1.0, f"expected cTCS=1.0 for valid TRAC trajectory, got {score}"
    print(f"  {PASS} test_trac_treated_patient_scores_perfect (cTCS={score})")


def test_trac_untreated_patient_a_pos_to_a_neg_flagged():
    """Untreated A+ -> A_neg is biologically implausible -> flagged."""
    pack = load_rulepack("ad/aa_2024_trac")
    traj = _make_trac_trajectory(
        states=["A_pos", "A_neg"],
        treatment_status=["none", "none"],
    )
    score = ctcs_per_patient(traj, pack)
    # 1 transition, 0 admissible
    assert score == 0.0, f"expected cTCS=0.0 for untreated A+ -> A-, got {score}"
    print(f"  {PASS} test_trac_untreated_patient_a_pos_to_a_neg_flagged "
          f"(cTCS={score})")


def test_trac_full_audit_cohort_pipeline():
    """Full audit() on a small TRAC cohort produces stable audit_id."""
    pack = load_rulepack("ad/aa_2024_trac")
    cohort = [
        # Patient 1: textbook TRAC responder
        _make_trac_trajectory(
            states=["A_pos", "Partial_TRAC", "Full_TRAC"],
            treatment_status=["anti_amyloid_active",
                               "anti_amyloid_active",
                               "anti_amyloid_active"],
            patient_id="TRAC_responder_01",
        ),
        # Patient 2: untreated, no progression
        _make_trac_trajectory(
            states=["A_neg", "A_neg", "A_pos"],
            treatment_status=["none", "none", "none"],
            interval_days=730,
            patient_id="TRAC_untreated_02",
        ),
        # Patient 3: untreated implausible clearance (should be flagged)
        _make_trac_trajectory(
            states=["A_pos", "A_neg"],
            treatment_status=["none", "none"],
            patient_id="TRAC_implausible_03",
        ),
    ]
    result = audit(cohort, pack, bootstrap_B=200, seed=42)
    assert result.n_patients_scored == 3
    # Patient 1: 2 transitions, both admissible
    # Patient 2: 2 transitions, both admissible
    # Patient 3: 1 transition, NOT admissible
    assert result.n_transitions == 5
    assert result.n_flagged == 1, (
        f"expected 1 flagged (untreated A+ -> A-), got {result.n_flagged}"
    )
    print(f"  {PASS} test_trac_full_audit_cohort_pipeline "
          f"(n_transitions={result.n_transitions}, "
          f"n_flagged={result.n_flagged}, cTCS={result.ctcs.ci.point:.4f})")


def test_trac_post_discontinuation_re_accumulation_admissible():
    """Full_TRAC -> Partial_TRAC under discontinued treatment is admissible."""
    pack = load_rulepack("ad/aa_2024_trac")
    traj = _make_trac_trajectory(
        states=["Full_TRAC", "Partial_TRAC"],
        treatment_status=["anti_amyloid_discontinued",
                           "anti_amyloid_discontinued"],
        interval_days=730,
    )
    score = ctcs_per_patient(traj, pack)
    assert score == 1.0
    print(f"  {PASS} test_trac_post_discontinuation_re_accumulation_admissible")


# ============================================================
# Runner
# ============================================================

def run_all():
    tests = [
        # Trajectory
        test_trajectory_length_and_transitions,
        test_trajectory_zero_length_ok,
        test_trajectory_single_visit_ok,
        test_trajectory_mismatched_lengths_fail,
        test_trajectory_descending_dates_fail,
        test_trajectory_with_probabilities,
        test_trajectory_probabilities_out_of_range_fail,
        test_trajectories_from_dataframe,
        # cTCS / pTCS / uTCS scoring
        test_ctcs_perfect_trajectory,
        test_ctcs_all_bad_trajectory,
        test_ctcs_mixed_trajectory,
        test_ctcs_self_loop_admissible,
        test_ctcs_none_for_single_visit,
        test_build_generator_for_ad_niaaa_2018,
        test_build_generator_population_priors,
        test_build_generator_no_priors_returns_none,
        test_ptcs_admissible_higher_than_inadmissible,
        test_utcs_with_probabilities,
        test_utcs_falls_back_to_ctcs_without_probabilities,
        test_score_cohort_aligned_arrays,
        # Bootstrap
        test_huber_equals_median_on_skewed_data,
        test_huber_equals_mean_on_clean_data,
        test_cluster_bootstrap_deterministic,
        test_cluster_bootstrap_ci_contains_point,
        test_cluster_bootstrap_bca_vs_percentile_similar_for_symmetric,
        test_cluster_bootstrap_narrower_ci_with_more_data,
        test_paired_bootstrap_difference,
        test_cluster_bootstrap_single_value_degenerate,
        # End-to-end audit
        test_audit_end_to_end_synthetic,
        test_audit_id_deterministic,
        test_audit_id_changes_with_seed,
        test_audit_with_probabilities_utcs_differs_from_ctcs,
        test_audit_ptcs_unavailable_on_aa_2024,
        test_audit_skeleton_rejected,
        # TRAC (schema v1.2 conditional admissibility)
        test_trac_treated_patient_scores_perfect,
        test_trac_untreated_patient_a_pos_to_a_neg_flagged,
        test_trac_full_audit_cohort_pipeline,
        test_trac_post_discontinuation_re_accumulation_admissible,
        # Real ADNI (skipped on CI)
        test_real_adni_audit_end_to_end,
    ]
    print(f"\nNeuroTCS audit_core tests — running {len(tests)} tests:\n")
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  {FAIL} {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  {FAIL} {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
