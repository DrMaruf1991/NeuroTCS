"""Tests for the cross_sheet/ad_crossmodal_coherence invariant pack."""
from __future__ import annotations

from neurotcs.cross_sheet.audit import audit_cross_sheet
from neurotcs.cross_sheet.loader import list_invariantpacks, load_invariantpack

PACK = "cross_sheet/ad_crossmodal_coherence"


def _pack():
    return load_invariantpack(PACK)


def _run(biomarkers=None, predictions=None):
    sub = {"manifest": {"conformance_level": "L2"}}
    if biomarkers is not None:
        sub["biomarkers"] = biomarkers
    if predictions is not None:
        sub["predictions"] = predictions
    return audit_cross_sheet(sub, [_pack()], dry_run=False)


class TestPackStructure:

    def test_pack_is_production(self):
        entry = [p for p in list_invariantpacks() if p["name"] == PACK]
        assert entry and entry[0]["status"] == "production"

    def test_every_invariant_has_citation(self):
        lp = _pack()
        for inv in lp.invariantpack.invariants:
            assert inv.citation is not None
            # at least a PMID or DOI must be present
            assert inv.citation.citation_pmid or inv.citation.citation_doi


class TestCrossModalCatches:

    def test_amyloid_positive_with_negative_centiloid(self):
        bio = [{"patient_id": "P1", "visit_id": 0,
                "amyloid_status": "positive", "amyloid_centiloid": 4.0}]
        r = _run(biomarkers=bio)
        names = {f.invariant_name for f in r.flags if f.severity != "info"}
        assert "amyloid_positive_status_requires_positive_centiloid" in names

    def test_cdr_global_zero_with_high_sob(self):
        bio = [{"patient_id": "P1", "visit_id": 0,
                "cdr_global": 0.0, "cdr_sob": 15.0}]
        r = _run(biomarkers=bio)
        names = {f.invariant_name for f in r.flags if f.severity != "info"}
        assert "cdr_global_zero_with_high_sum_of_boxes" in names

    def test_tau_visual_read_negative_with_positive_suvr(self):
        bio = [{"patient_id": "P1", "visit_id": 0,
                "tau_visual_read_negative_flag": 1.0,
                "tau_pet_neocortical_uptake_ratio_flortaucipir": 1.8}]
        r = _run(biomarkers=bio)
        names = {f.invariant_name for f in r.flags if f.severity != "info"}
        assert "tau_visual_read_negative_with_positive_suvr" in names

    def test_ptau181_grossly_exceeds_ptau217(self):
        bio = [{"patient_id": "P1", "visit_id": 0,
                "plasma_ptau181_pgml": 2.5, "plasma_ptau217_pgml": 0.15}]
        r = _run(biomarkers=bio)
        names = {f.invariant_name for f in r.flags if f.severity != "info"}
        assert "ptau181_grossly_exceeds_ptau217" in names

    def test_moca_grossly_exceeds_mmse(self):
        bio = [{"patient_id": "P1", "visit_id": 0, "moca": 29.0, "mmse": 18.0}]
        r = _run(biomarkers=bio)
        names = {f.invariant_name for f in r.flags if f.severity != "info"}
        assert "moca_grossly_exceeds_mmse" in names


class TestNoFalsePositives:

    def test_concordant_data_clean(self):
        # amyloid-positive WITH positive centiloid, concordant scores -> no flags
        bio = [{"patient_id": "P1", "visit_id": 0,
                "amyloid_status": "positive", "amyloid_centiloid": 88.0,
                "cdr_global": 1.0, "cdr_sob": 6.0,
                "moca": 18.0, "mmse": 22.0,
                "plasma_ptau181_pgml": 0.3, "plasma_ptau217_pgml": 0.5}]
        r = _run(biomarkers=bio)
        non_info = [f for f in r.flags if f.severity != "info"]
        assert non_info == []
