"""Tests for the NIA-AA 2024 numeric clinical staging pack (stages 0-6).

These prove BOTH halves of the admissibility rule independently of any external
dataset:
  - regression OUT of dementia (4/5/6 -> strictly lower) is INADMISSIBLE;
  - pre-dementia reversion (within 0-3) is ADMISSIBLE and never flagged
    (the false-positive trap the pack exists to avoid);
  - forward progression and progression into dementia are admissible;
  - the pack carries NO rate / fast-progression logic.

Source: Jack CR Jr et al. 2024, "Revised criteria for diagnosis and staging of
Alzheimer's disease: Alzheimer's Association Workgroup", Alzheimer's & Dementia
2024;20(8):5143-5169, Table 6 (PMID 38934362; DOI 10.1002/alz.13859).
"""
from __future__ import annotations

from neurotcs.rulepack.loader import load_rulepack

PACK = "ad/niaaa_2024_clinical_numeric"
PMID = "38934362"
DOI = "10.1002/alz.13859"
STAGES = ["0", "1", "2", "3", "4", "5", "6"]
DEMENTIA = {"4", "5", "6"}


def _load():
    return load_rulepack(PACK).rulepack


def test_pack_loads_as_production():
    assert load_rulepack(PACK).is_production


def test_state_space_is_exactly_0_through_6():
    rp = _load()
    assert [s.name for s in rp.state_space] == STAGES


def test_anchor_citation_is_jack_2024():
    rp = _load()
    a = rp.anchor_citation
    assert a.citation_pmid == PMID
    assert a.citation_doi == DOI


def _adm(rp):
    return {(t.from_state, t.to_state) for t in rp.admissible_transitions}


def _inadm(rp):
    return {(t.from_state, t.to_state) for t in rp.inadmissible_transitions}


def test_every_out_of_dementia_regression_is_inadmissible():
    """4/5/6 -> any strictly lower stage must be inadmissible (and not also
    listed admissible)."""
    rp = _load()
    inadm, adm = _inadm(rp), _adm(rp)
    expected = []
    for fi, f in enumerate(STAGES):
        if f not in DEMENTIA:
            continue
        for ti, t in enumerate(STAGES):
            if ti < fi:
                expected.append((f, t))
    assert len(expected) == 15  # 4->{0..3}=4, 5->{0..4}=5, 6->{0..5}=6
    for pair in expected:
        assert pair in inadm, f"{pair} should be inadmissible"
        assert pair not in adm, f"{pair} must not also be admissible"


def test_pre_dementia_reversion_is_admissible_never_inadmissible():
    """Reversion within stages 0-3 must be admissible and never flagged."""
    rp = _load()
    inadm, adm = _inadm(rp), _adm(rp)
    for fi in range(0, 4):
        for ti in range(0, fi):
            pair = (STAGES[fi], STAGES[ti])
            assert pair in adm, f"{pair} pre-dementia reversion should be admissible"
            assert pair not in inadm, f"{pair} must not be inadmissible"


def test_forward_progression_admissible_including_into_dementia():
    rp = _load()
    adm = _adm(rp)
    # a representative span of forward moves, incl. 3->4 (into dementia) and 0->6
    for pair in [("0", "1"), ("2", "3"), ("3", "4"), ("4", "5"), ("5", "6"), ("0", "6")]:
        assert pair in adm, f"{pair} forward progression should be admissible"


def test_dementia_worsening_is_not_flagged():
    rp = _load()
    inadm = _inadm(rp)
    for pair in [("4", "5"), ("4", "6"), ("5", "6")]:
        assert pair not in inadm, f"{pair} dementia worsening must not be inadmissible"


def test_no_rate_or_fast_progression_logic():
    """The clinical pack must carry no min/max interval gating on transitions
    (no invented time floor); intervals are null."""
    rp = _load()
    for t in rp.admissible_transitions:
        assert getattr(t, "min_delta_t_days", None) is None
        assert getattr(t, "max_delta_t_days", None) is None


def test_every_transition_is_citation_anchored():
    rp = _load()
    for t in rp.admissible_transitions:
        assert t.citation is not None
        assert t.citation.citation_pmid == PMID or t.citation.citation_doi == DOI
    for t in rp.inadmissible_transitions:
        assert t.citation is not None
        assert t.citation.citation_pmid == PMID or t.citation.citation_doi == DOI
