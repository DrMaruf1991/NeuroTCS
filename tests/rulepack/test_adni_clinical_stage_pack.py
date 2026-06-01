"""Tests for the ADNI clinical-stage rule pack (ad/adni_clinical_stage).

Locks the external-auditor design decisions so a future edit cannot silently
reintroduce the false-flag traps:
  * EMCI/LMCI are SEVERITY STRATA -> severity skips (CN->LMCI) are admissible.
  * REVERSION is real -> EMCI->CN, LMCI->EMCI, MCI->CN are admissible.
  * Only single-step reversion OUT of AD dementia is inadmissible.
  * The pack recognizes the full ADNI vocabulary and the selector routes to it.
"""
from __future__ import annotations

import pandas as pd

from neurotcs.audit_core import audit, trajectories_from_dataframe
from neurotcs.orchestration.vocabulary import select_rulepack_or_refuse
from neurotcs.rulepack.loader import load_rulepack

PACK = "ad/adni_clinical_stage"


def _audit(seqs):
    """seqs: {pid: [(date, state), ...]} -> (n_flagged, flags_in_order)."""
    rows = []
    for pid, seq in seqs.items():
        for d, s in seq:
            rows.append({"pid": pid, "date": d, "state": s})
    df = pd.DataFrame(rows)
    trajs = trajectories_from_dataframe(
        df, patient_id_col="pid", visit_date_col="date", state_col="state")
    res = audit(trajs, load_rulepack(PACK), bootstrap_B=200,
                return_per_transition=True)
    pt = res.per_transition
    return pt.n_flagged, list(pt.flags)


class TestPackStructure:

    def test_loads_as_production(self):
        lp = load_rulepack(PACK)
        assert str(lp.rulepack.status).endswith("PRODUCTION")
        names = [s.name for s in lp.rulepack.state_space]
        assert names == ["CN", "SMC", "EMCI", "LMCI", "MCI", "AD"]

    def test_has_endorsing_bodies(self):
        lp = load_rulepack(PACK)
        assert len(lp.rulepack.endorsing_bodies) >= 5

    def test_ad_out_transitions_are_inadmissible(self):
        lp = load_rulepack(PACK)
        inadm = {(t.from_state, t.to_state)
                 for t in lp.rulepack.inadmissible_transitions}
        for to in ("CN", "SMC", "EMCI", "LMCI", "MCI"):
            assert ("AD", to) in inadm


class TestVocabularyRouting:

    def test_adni_emci_lmci_cohort_routes_here(self):
        # Previously REFUSED (niaaa_2018 lacks EMCI/LMCI).
        pack, m = select_rulepack_or_refuse(["CN", "EMCI", "LMCI", "AD"])
        assert pack == PACK
        assert m.unmatched == ()

    def test_full_adni_vocabulary_no_contamination(self):
        pack, m = select_rulepack_or_refuse(
            ["CN", "SMC", "EMCI", "LMCI", "MCI", "AD"])
        assert pack == PACK
        assert m.coverage_fraction == 1.0
        assert m.unmatched == ()

    def test_cn_mci_ad_still_routes_to_niaaa(self):
        # No regression: the canonical 3-state cohort prefers niaaa_2018.
        pack, _ = select_rulepack_or_refuse(["CN", "MCI", "AD"])
        assert pack == "ad/niaaa_2018"


class TestAuditDiscipline:

    def test_clean_progression_not_flagged(self):
        n, _ = _audit({"P1": [("2018-01-01", "CN"), ("2019-01-01", "EMCI"),
                              ("2020-01-01", "LMCI"), ("2021-06-01", "AD")]})
        assert n == 0

    def test_severity_skip_admissible(self):
        # CN->LMCI skipping EMCI: EMCI/LMCI are strata, not obligatory stages.
        n, _ = _audit({"P": [("2018-01-01", "CN"), ("2019-06-01", "LMCI")]})
        assert n == 0

    def test_emci_to_cn_reversion_admissible(self):
        # ~31% of EMCI revert to normal by year 2 -- must NOT be flagged.
        n, _ = _audit({"P": [("2018-01-01", "EMCI"), ("2019-06-01", "CN")]})
        assert n == 0

    def test_lmci_to_emci_reversion_admissible(self):
        n, _ = _audit({"P": [("2018-01-01", "LMCI"), ("2019-06-01", "EMCI")]})
        assert n == 0

    def test_ad_to_cn_is_flagged(self):
        # The one transition that MUST flag: dementia -> normal in one step.
        n, flags = _audit({"P": [("2018-01-01", "AD"), ("2019-06-01", "CN")]})
        assert n == 1
        assert bool(flags[0]) is True

    def test_mixed_cohort_only_ad_reversion_flagged(self):
        n, flags = _audit({
            "P1": [("2018-01-01", "CN"), ("2019-01-01", "EMCI"),
                   ("2020-01-01", "LMCI"), ("2021-06-01", "AD")],   # 3 clean
            "P2": [("2018-01-01", "CN"), ("2019-06-01", "LMCI")],   # skip: clean
            "P3": [("2018-01-01", "EMCI"), ("2019-01-01", "CN")],   # reversion: clean
            "P4": [("2018-01-01", "AD"), ("2019-06-01", "CN")],     # AD->CN: FLAG
        })
        assert n == 1
        assert bool(flags[-1]) is True  # the AD->CN transition (last)
