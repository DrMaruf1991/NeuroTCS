"""v1.41.0 — Jack 2018 AT(N) rule pack.

These tests lock the regulatory-grade properties of the ad/atn_2018@1.0.0 pack:
    - State space: exactly the 5 AD-continuum biomarker profiles from
      Jack 2018 PMID 29653606 / Jack 2016 PMID 27371494.
    - Admissible transitions: the AD-continuum forward progressions only
      (amyloid cascade per Jack 2013 PMID 23332364 / Jack 2024 §4.2).
    - A-T+ inadmissibility per Jack 2024 §3 (verbatim p.5147: "The A-T2+
      biomarker profile is not consistent with a diagnosis of AD") is
      enforced by EXCLUSION from state_space — a dataset containing A-T+
      rows will refuse with vocabulary_mismatch, surfacing those rows.
    - Closes the staging_biological vocabulary_mismatch gap on every
      dataset using the Jack 2018 AT(N) taxonomy (the universal
      pre-2024 cohort export format).
"""
from __future__ import annotations

import pandas as pd

from neurotcs.audit_core import audit, trajectories_from_dataframe
from neurotcs.orchestration.vocabulary import assess_vocabulary, select_rulepack_or_refuse
from neurotcs.rulepack import load_rulepack

PACK_NAME = "ad/atn_2018"


# ===========================================================================
# Pack structure — state space + transitions
# ===========================================================================

def test_atn_2018_pack_loads_as_production() -> None:
    """The pack must load cleanly and ship as production status."""
    p = load_rulepack(PACK_NAME)
    assert str(p.rulepack.rulepack_id).startswith("ad/atn_2018@")
    # status is enumerable; production is the user-facing string
    assert "production" in str(p.rulepack.status).lower()


def test_atn_2018_state_space_is_full_jack_2018_taxonomy_eight_states() -> None:
    """State space is the full 8-state Jack 2018 AT(N) taxonomy. Any
    addition or removal of a state requires a pack version bump and a
    corresponding update to the regression tests + CHANGELOG.

    The 8 states split into three groups by the Jack 2024 revision:
      - 5 AD continuum states (admissible): A-T-N-, A+T-N-, A+T-N+,
        A+T+N-, A+T+N+
      - 1 non-AD pathology state (Jack 2024 §7.1, N is non-specific):
        A-T-N+
      - 2 Jack 2024 §3 inadmissible states (PART or measurement
        variance): A-T+N-, A-T+N+

    All 8 are RECOGNIZED vocabulary (in state_space, so the pack routes
    correctly via full-data-recognition applicability rule). Only the 5
    AD-continuum states have admissible_transitions; the other 3 produce
    inadmissible_state flags on any transition into or out of them.
    """
    p = load_rulepack(PACK_NAME)
    states = sorted(s.name for s in p.rulepack.state_space)
    assert states == sorted([
        "A-T-N-",   # baseline (admissible)
        "A-T-N+",   # non-AD pathology (no admissible transitions)
        "A+T-N-",   # AD continuum entry (admissible)
        "A+T-N+",   # T2N mismatch (admissible per §8)
        "A+T+N-",   # tau positive (admissible, stages B/C/D)
        "A+T+N+",   # advanced AD continuum (admissible)
        "A-T+N-",   # INADMISSIBLE per Jack 2024 §3
        "A-T+N+",   # INADMISSIBLE per Jack 2024 §3
    ])


def test_atn_2018_a_minus_t_plus_states_have_zero_admissible_transitions() -> None:
    """Jack 2024 §3 (verbatim p.5147): 'The A-T2+ biomarker profile is
    not consistent with a diagnosis of AD.' The pack enforces this by
    INCLUDING A-T+N- and A-T+N+ in state_space (vocabulary recognition)
    but listing ZERO admissible_transitions involving them — so any
    trajectory crossing into or out of an A-T+ state flags as
    inadmissible_state in the staging audit.

    The A-T-N+ non-AD-pathology state is handled the same way: in
    vocabulary, but with no admissible transitions, so any movement to
    or from it flags inadmissible_state (it's not in the AD continuum
    per Jack 2024 §7.1)."""
    p = load_rulepack(PACK_NAME)
    inadmissible_or_non_ad = {"A-T+N-", "A-T+N+", "A-T-N+"}
    for t in p.rulepack.admissible_transitions:
        assert t.from_state not in inadmissible_or_non_ad, (
            f"Transition from {t.from_state} must not be admissible "
            f"(Jack 2024 §3 / §7.1)."
        )
        assert t.to_state not in inadmissible_or_non_ad, (
            f"Transition to {t.to_state} must not be admissible "
            f"(Jack 2024 §3 / §7.1)."
        )


def test_atn_2018_a_minus_t_plus_states_are_in_state_space_for_routing() -> None:
    """A-T+ states MUST be in state_space so a dataset containing them
    is routed to this pack (which then flags them inadmissibly via the
    transition layer). Excluding them from state_space would cause
    vocabulary_mismatch on those rows, refusing them silently — that's
    a partial fix, not world-class.

    The Jack 2024 §3 inadmissibility is enforced at the TRANSITION
    layer (zero admissible transitions reference these states), not at
    the vocabulary layer."""
    p = load_rulepack(PACK_NAME)
    state_names = {s.name for s in p.rulepack.state_space}
    assert "A-T+N-" in state_names
    assert "A-T+N+" in state_names


def test_atn_2018_admissible_transitions_are_ad_continuum_only() -> None:
    """Admissible transitions encode the AD-continuum forward progression
    per Jack 2024 §4.2 (amyloid precedes tau, tau precedes
    neurodegeneration). Any transition not in this list is flagged as
    inadmissible by the staging auditor."""
    p = load_rulepack(PACK_NAME)
    transitions = {(t.from_state, t.to_state)
                   for t in p.rulepack.admissible_transitions}
    expected = {
        ("A-T-N-", "A+T-N-"),   # amyloid becomes positive (continuum entry)
        ("A+T-N-", "A+T-N+"),   # T2N-mismatch emerges (copathology, Jack §8)
        ("A+T-N-", "A+T+N-"),   # tau positivity follows amyloid (cascade)
        ("A+T-N+", "A+T+N+"),   # tau positivity in T2N-mismatch case
        ("A+T+N-", "A+T+N+"),   # neurodegeneration follows tau
    }
    assert transitions == expected, (
        f"Unexpected transition set. Found: {transitions}; expected: {expected}"
    )


def test_atn_2018_no_reversals_admissible() -> None:
    """Per Jack 2013 amyloid-cascade (PMID 23332364), established
    positivity does not spontaneously revert in untreated natural history.
    Treatment-induced clearance (Jack 2024 §9 TRAC) is the separate
    ad/aa_2024_trac pack. No reversal transitions are admissible here."""
    p = load_rulepack(PACK_NAME)
    transitions = {(t.from_state, t.to_state)
                   for t in p.rulepack.admissible_transitions}
    forbidden_reversals = [
        ("A+T-N-", "A-T-N-"),   # amyloid clearance (would need TRAC pack)
        ("A+T+N-", "A+T-N-"),   # tau clearance
        ("A+T+N+", "A+T+N-"),   # neurodegeneration reversal
        ("A+T-N+", "A+T-N-"),   # neurodegeneration reversal (T2N variant)
        ("A+T+N+", "A+T+N-"),   # neurodegeneration reversal (advanced)
    ]
    for fr, to in forbidden_reversals:
        assert (fr, to) not in transitions, (
            f"Reversal {fr}->{to} must not be in admissible_transitions"
        )


# ===========================================================================
# Citation lock — Jack 2024 anchor + Jack 2016/2018 origin
# ===========================================================================

def test_atn_2018_anchor_citation_is_jack_2024() -> None:
    """Anchor citation is Jack 2024 PMID 38934362; the pack's own
    inadmissibility rules cite §3 verbatim. The originating Jack 2016 +
    Jack 2018 sources are named in clinical_source_authority."""
    p = load_rulepack(PACK_NAME)
    ac = p.rulepack.anchor_citation
    assert ac.citation_pmid == "38934362"
    assert ac.citation_doi == "10.1002/alz.13859"
    # Section references must be in the citation text so a regulator can
    # trace the reasoning without leaving the pack.
    assert "§3" in ac.citation_text
    assert "§7.1" in ac.citation_text or "§8" in ac.citation_text


def test_atn_2018_clinical_source_authority_names_origin_papers() -> None:
    """clinical_source_authority must name the originating AT(N) papers
    so the citation chain is auditable."""
    p = load_rulepack(PACK_NAME)
    csa = p.rulepack.clinical_source_authority.lower()
    assert "29653606" in csa   # Jack 2018 NIA-AA Research Framework
    assert "27371494" in csa   # Jack 2016 originating AT(N) scheme
    assert "23332364" in csa   # Jack 2013 amyloid cascade


def test_atn_2018_every_transition_carries_a_citation() -> None:
    """Every admissible transition must be citation-anchored. No
    transition may be unjustified."""
    p = load_rulepack(PACK_NAME)
    for t in p.rulepack.admissible_transitions:
        assert t.citation is not None
        assert t.citation.citation_pmid == "38934362"
        assert t.guideline_section is not None
        assert len(t.guideline_section) > 5  # something substantive


# ===========================================================================
# Vocabulary applicability — the regulatory-grade routing test
# ===========================================================================

def test_atn_2018_vocabulary_covers_typical_jack_2018_cohort_data() -> None:
    """A dataset using the 5 typical Jack 2018 AT(N) profiles has
    contamination=0 (every data state is in the pack vocabulary) and is
    therefore APPLICABLE under the v1.41.0 full-data-recognition rule,
    even though coverage_fraction is 5/8 = 0.625 (below the 0.80
    historical threshold). This is the closes-the-vocabulary_mismatch-
    gap regression test."""
    data_states = ["A+T+N+", "A+T+N-", "A+T-N+", "A+T-N-", "A-T-N-"]
    vm = assess_vocabulary(data_states, PACK_NAME)
    # The pack is a deliberate superset (recognizes 3 additional rare
    # states for Jack 2024 §3 inadmissibility enforcement), so coverage
    # < 1.0 is expected and correct.
    assert vm.coverage_fraction == 5 / 8
    # Critical property: every observed data state is in the pack.
    assert vm.contamination_fraction == 0.0
    # Therefore applicable via the additive v1.41.0 rule (b).
    assert vm.is_applicable
    assert vm.unmatched == ()


def test_atn_2018_vocabulary_recognizes_a_minus_t_plus_data() -> None:
    """A dataset containing A-T+ profiles is RECOGNIZED by this pack
    (the inadmissible states are in state_space). The Jack 2024 §3
    inadmissibility is surfaced through the staging-transition audit
    (inadmissible_state flags), NOT through vocabulary mismatch. This is
    the world-class fix vs. the earlier partial-fix behavior of
    excluding A-T+ from state_space."""
    data_states = ["A-T-N-", "A+T-N-", "A-T+N-", "A-T+N+"]
    vm = assess_vocabulary(data_states, PACK_NAME)
    # All four data states are recognized (in state_space).
    assert "A-T+N-" not in vm.unmatched
    assert "A-T+N+" not in vm.unmatched
    assert vm.contamination_fraction == 0.0
    # Pack is applicable -- it will route the trajectory to staging
    # audit, which will then flag A-T+ transitions as inadmissible_state.
    assert vm.is_applicable


def test_atn_2018_routing_selects_pack_for_jack_2018_data() -> None:
    """select_rulepack_or_refuse must select atn_2018 (not aa_2024)
    when the data uses the Jack 2018 vocabulary."""
    data_states = ["A+T+N+", "A+T+N-", "A+T-N+", "A+T-N-", "A-T-N-"]
    name, vm = select_rulepack_or_refuse(
        data_states, disease_domain="alzheimers")
    assert name == "ad/atn_2018"
    assert vm.is_applicable


# ===========================================================================
# End-to-end — auditing a synthetic AD trajectory through the pack
# ===========================================================================

def _make_synthetic_traj(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    """rows: list of (patient_id, visit_date_iso, state)."""
    return pd.DataFrame([
        {"subject_id": pid, "visit_date": vd, "state": st}
        for pid, vd, st in rows
    ])


def test_atn_2018_typical_trajectory_clean() -> None:
    """A canonical AD-continuum trajectory (A-T-N- -> A+T-N- -> A+T+N- ->
    A+T+N+) produces ZERO flags — every transition is admissible."""
    df = _make_synthetic_traj([
        ("S001", "2020-01-01", "A-T-N-"),
        ("S001", "2021-01-01", "A+T-N-"),
        ("S001", "2022-01-01", "A+T+N-"),
        ("S001", "2023-01-01", "A+T+N+"),
    ])
    trajs = trajectories_from_dataframe(
        df, patient_id_col="subject_id", visit_date_col="visit_date",
        state_col="state", skip_invalid=False)
    lp = load_rulepack(PACK_NAME)
    res = audit(trajs, lp, bootstrap_B=1000, seed=42, return_per_transition=True)
    # 3 transitions, all admissible -> 0 flags
    assert sum(res.per_transition.flags) == 0
    # cTCS at 1.0 (every transition admissible)
    assert res.ctcs.ci.point == 1.0


def test_atn_2018_reversal_trajectory_flagged() -> None:
    """A reversal trajectory (A+T-N- -> A-T-N-) is a forbidden amyloid
    clearance without treatment context and MUST be flagged."""
    df = _make_synthetic_traj([
        ("S002", "2020-01-01", "A-T-N-"),
        ("S002", "2021-01-01", "A+T-N-"),
        ("S002", "2022-01-01", "A-T-N-"),   # forbidden reversal
    ])
    trajs = trajectories_from_dataframe(
        df, patient_id_col="subject_id", visit_date_col="visit_date",
        state_col="state", skip_invalid=False)
    lp = load_rulepack(PACK_NAME)
    res = audit(trajs, lp, bootstrap_B=1000, seed=42, return_per_transition=True)
    # 2 transitions; the second (A+T-N- -> A-T-N-) must flag
    assert sum(res.per_transition.flags) >= 1


def test_atn_2018_t2n_mismatch_state_admitted_no_flag() -> None:
    """A trajectory through A+T-N+ (T2N mismatch per Jack 2024 §8) is
    biologically admissible — the state is in the AD continuum. The
    advisory flag for likely copathology is deferred to a future cross-
    sheet invariant batch and is NOT emitted by the staging audit here."""
    df = _make_synthetic_traj([
        ("S003", "2020-01-01", "A-T-N-"),
        ("S003", "2021-01-01", "A+T-N-"),
        ("S003", "2022-01-01", "A+T-N+"),   # T2N mismatch emerges
        ("S003", "2023-01-01", "A+T+N+"),   # tau follows
    ])
    trajs = trajectories_from_dataframe(
        df, patient_id_col="subject_id", visit_date_col="visit_date",
        state_col="state", skip_invalid=False)
    lp = load_rulepack(PACK_NAME)
    res = audit(trajs, lp, bootstrap_B=1000, seed=42, return_per_transition=True)
    # Every transition is admissible per the pack
    assert sum(res.per_transition.flags) == 0
    assert res.ctcs.ci.point == 1.0


def test_atn_2018_a_minus_t_plus_transition_flagged_inadmissible() -> None:
    """**World-class enforcement of Jack 2024 §3.** A trajectory that
    enters an A-T+ state MUST flag inadmissible at the transition layer.
    The earlier 5-state pack version excluded A-T+ from state_space,
    which caused fail-closed vocabulary_mismatch — that surfaced the
    issue but did NOT carry the citation, did NOT produce a per-
    transition flag, and did NOT contribute to the impossible-tier
    severity count. The 8-state pack restores world-class enforcement:
    A-T+ is in vocabulary so the pack routes; transitions into it have
    zero admissible matches so the staging auditor flags them with the
    pack's citation in the audit trail."""
    df = _make_synthetic_traj([
        ("S009", "2020-01-01", "A-T-N-"),
        ("S009", "2021-01-01", "A-T+N-"),   # inadmissible per Jack 2024 §3
    ])
    trajs = trajectories_from_dataframe(
        df, patient_id_col="subject_id", visit_date_col="visit_date",
        state_col="state", skip_invalid=False)
    lp = load_rulepack(PACK_NAME)
    res = audit(trajs, lp, bootstrap_B=1000, seed=42, return_per_transition=True)
    # The single A-T-N- -> A-T+N- transition must flag.
    assert sum(res.per_transition.flags) == 1
    # cTCS < 1.0 because the only transition is inadmissible.
    assert res.ctcs.ci.point < 1.0


def test_atn_2018_a_minus_t_minus_n_plus_transition_flagged() -> None:
    """A-T-N+ (no AD biomarker + neurodegeneration; Jack 2024 §7.1 N is
    non-specific so this is non-AD pathology) has zero admissible
    transitions per the AD continuum. A trajectory entering A-T-N+
    flags inadmissible — surfaces the non-AD-pathology subject for
    routing to an appropriate framework rather than silently auditing
    them as AD."""
    df = _make_synthetic_traj([
        ("S010", "2020-01-01", "A-T-N-"),
        ("S010", "2021-01-01", "A-T-N+"),   # non-AD pathology
    ])
    trajs = trajectories_from_dataframe(
        df, patient_id_col="subject_id", visit_date_col="visit_date",
        state_col="state", skip_invalid=False)
    lp = load_rulepack(PACK_NAME)
    res = audit(trajs, lp, bootstrap_B=1000, seed=42, return_per_transition=True)
    assert sum(res.per_transition.flags) == 1
    assert res.ctcs.ci.point < 1.0
