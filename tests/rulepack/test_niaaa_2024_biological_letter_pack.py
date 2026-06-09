"""Tests for the NIA-AA 2024 BIOLOGICAL letter staging pack (A/B/C/D).

Proves BOTH branches independently of any dataset:
  - forward A->B->C->D (incl. skips) admissible;
  - any backward letter step is inadmissible UNLESS the regressing (to) visit
    carries treatment_status == "TRAC" (the TRAC carve-out, La Joie 2025);
  - the carve-out is row-local to the regressing visit (conditions_evaluated_at
    = to_visit);
  - no rate / fast-progression logic.

The carve-out branch (a backward step that LANDS on a TRAC row) is proven here
directly, because a real dataset almost never contains that exact coincidence.

Sources: Jack CR Jr et al. 2024 (PMID 38934362; DOI 10.1002/alz.13859) PET-based
biological staging A/B/C/D; La Joie et al. 2025 TRAC (DOI 10.1002/alz.70997).
"""
from __future__ import annotations

from datetime import date

from neurotcs.audit_core.trajectory import Trajectory
from neurotcs.rulepack.loader import load_rulepack

PACK = "ad/niaaa_2024_biological_letter"
LETTERS = ["A", "B", "C", "D"]
RANK = {"A": 0, "B": 1, "C": 2, "D": 3}


def _load():
    return load_rulepack(PACK).rulepack


def test_pack_loads_as_production():
    assert load_rulepack(PACK).is_production


def test_state_space_is_A_B_C_D():
    assert [s.name for s in _load().state_space] == LETTERS


def test_anchor_citation_is_jack_2024():
    a = _load().anchor_citation
    assert a.citation_pmid == "38934362"
    assert a.citation_doi == "10.1002/alz.13859"


def test_no_unconditional_inadmissible_transitions():
    # backward steps are expressed as TRAC-gated admissible transitions, so the
    # inadmissible_transitions list is empty (fail-closed when TRAC absent).
    assert _load().inadmissible_transitions == []


def test_forward_transitions_admissible_unconditional():
    rp = _load()
    adm = {(t.from_state, t.to_state): t for t in rp.admissible_transitions}
    for f in LETTERS:
        for to in LETTERS:
            if RANK[to] > RANK[f]:
                assert (f, to) in adm, f"forward {f}->{to} should be admissible"
                assert not adm[(f, to)].required_conditions, \
                    f"forward {f}->{to} must be unconditional"


def test_every_backward_step_is_trac_gated_at_to_visit():
    rp = _load()
    adm = {(t.from_state, t.to_state): t for t in rp.admissible_transitions}
    n = 0
    for f in LETTERS:
        for to in LETTERS:
            if RANK[to] < RANK[f]:
                n += 1
                t = adm.get((f, to))
                assert t is not None, f"backward {f}->{to} should exist as gated admissible"
                assert (t.required_conditions or {}).get("treatment_status") == ["TRAC"]
                assert t.conditions_evaluated_at == "to_visit"
    assert n == 6  # B->A, C->A, C->B, D->A, D->B, D->C


def _adm(rp, states, tx):
    tr = Trajectory(patient_id="x", states=tuple(states),
                    dates=tuple(date(2020 + i, 1, 1) for i in range(len(states))),
                    treatment_status=tuple(tx))
    out = []
    for f, to, dt, fc, tc in tr.transitions_with_context():
        ok, _ = rp.is_admissible(f, to, dt, fc, tc)
        out.append(ok)
    return out


def test_untreated_backward_step_is_flagged():
    rp = _load()
    # C->B with no TRAC on the regressing visit => not admissible (flagged)
    assert _adm(rp, ["C", "B"], ["none", "none"]) == [False]
    # multi-step D->A untreated => flagged
    assert _adm(rp, ["D", "A"], ["none", "none"]) == [False]


def test_backward_step_on_trac_row_is_admissible():
    """The carve-out branch the dataset can't exercise: regression that lands on
    a TRAC row is valid (treatment-related amyloid clearance)."""
    rp = _load()
    assert _adm(rp, ["C", "B"], ["none", "TRAC"]) == [True]
    assert _adm(rp, ["D", "A"], ["none", "TRAC"]) == [True]


def test_trac_carveout_is_row_local_to_regressing_visit():
    """TRAC on the FROM visit (not the regressing TO visit) must NOT excuse."""
    rp = _load()
    # TRAC only on the earlier visit; regressing visit untreated => still flagged
    assert _adm(rp, ["C", "B"], ["TRAC", "none"]) == [False]


def test_forward_step_admissible_regardless_of_treatment():
    rp = _load()
    assert _adm(rp, ["A", "C"], ["none", "none"]) == [True]
    assert _adm(rp, ["B", "D"], ["none", "TRAC"]) == [True]


def test_no_rate_logic_on_transitions():
    rp = _load()
    for t in rp.admissible_transitions:
        assert getattr(t, "min_delta_t_days", None) is None
        assert getattr(t, "max_delta_t_days", None) is None
