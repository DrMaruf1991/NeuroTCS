"""v1.53.0 -- T2N-mismatch copathology advisory (Jack 2024 Sec 8).

Tests the new rowwise_conjunction_advisory condition type and the
cross_sheet/copathology_advisory pack that uses it. The advisory fires only on
the genuine A+ / T2- / N+ pattern, is INFO severity (the subject still has AD),
and -- being research_preview -- is refused in a production (dry_run=False)
audit.
"""
from __future__ import annotations

import pytest

from neurotcs.cross_sheet import (
    audit_cross_sheet,
    list_invariantpacks,
    load_invariantpack,
)

PACK = "cross_sheet/copathology_advisory"
INV = "t2n_mismatch_copathology_advisory"


def _advisories(flags):
    return [f for f in flags if f.invariant_name == INV]


def _row(pid, a, t, n):
    return {"patient_id": pid, "visit_id": "v1", "amyloid_status": a,
            "tau_status": t, "neurodegeneration_status": n}


def test_pack_loads_and_is_valid():
    listed = [d for d in list_invariantpacks() if d["name"] == PACK]
    assert listed and listed[0]["status"] != "INVALID", listed
    lp = load_invariantpack(PACK)
    assert len(lp.invariantpack.invariants) == 1
    assert lp.invariantpack.invariants[0].flag_severity == "info"


def test_fires_only_on_t2n_mismatch():
    lp = load_invariantpack(PACK)
    sub = {"biomarkers": [
        _row("P1", "positive", "negative", "present"),   # MISMATCH -> flag
        _row("P2", "positive", "positive", "present"),    # canonical AD -> no
        _row("P3", "positive", "negative", "absent"),     # stage A -> no
        _row("P4", "negative", "negative", "present"),    # not A+ -> no
    ]}
    adv = _advisories(audit_cross_sheet(sub, [lp], dry_run=True).flags)
    assert len(adv) == 1
    assert adv[0].join_key_values["patient_id"] == "P1"


def test_advisory_is_info_severity():
    lp = load_invariantpack(PACK)
    sub = {"biomarkers": [_row("P1", "positive", "negative", "present")]}
    adv = _advisories(audit_cross_sheet(sub, [lp], dry_run=True).flags)
    assert adv and adv[0].severity == "info"


def test_research_preview_refused_in_production():
    lp = load_invariantpack(PACK)
    sub = {"biomarkers": [_row("P1", "positive", "negative", "present")]}
    with pytest.raises(ValueError):
        audit_cross_sheet(sub, [lp], dry_run=False)


def test_missing_field_skips_row_not_flag():
    lp = load_invariantpack(PACK)
    # neurodegeneration_status absent -> conjunction cannot be established
    sub = {"biomarkers": [
        {"patient_id": "P1", "visit_id": "v1",
         "amyloid_status": "positive", "tau_status": "negative"},
    ]}
    adv = _advisories(audit_cross_sheet(sub, [lp], dry_run=True).flags)
    assert len(adv) == 0


class TestRowwiseConjunctionConditionType:
    """Unit-level coverage of the new condition type (mixed categorical +
    numeric predicates, validation)."""

    def test_numeric_predicate_conjunction(self):
        from datetime import date

        from neurotcs.clinical_ranges.schema import Citation, CitationStrength
        from neurotcs.cross_sheet.loader import LoadedInvariantPack
        from neurotcs.cross_sheet.schema import (
            CrossSheetInvariant,
            InvariantPack,
            InvariantPackStatus,
            RowPredicate,
            RowwiseConjunctionAdvisoryCondition,
            SheetSpec,
        )

        def cit():
            return Citation(
                citation_pmid="38934362",
                citation_text="Test citation, sufficient length for validator.",
                public_url="https://doi.org/10.1002/alz.13859",
                endorsing_bodies=["A", "B", "C", "D", "E"])

        cond = RowwiseConjunctionAdvisoryCondition(
            sheet="biomarkers",
            predicates=[
                RowPredicate(field="centiloid", operator="ge", threshold=25.0),
                RowPredicate(field="tau_suvr", operator="lt", threshold=1.2),
            ],
            advisory_message="amyloid+ centiloid with low tau SUVR (advisory).")
        inv = CrossSheetInvariant(
            name="numeric_conjunction_test",
            description="numeric conjunction advisory test.",
            sheets_required=[SheetSpec(role="biomarkers")],
            join_keys=["patient_id"], condition=cond, flag_severity="info",
            citation=cit(),
            citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
            guideline_section="test")
        pack = InvariantPack(
            schema_version="1.0.0",
            invariantpack_id="cross_sheet/test/numconj@1.0.0",
            pack_version="1.0.0", effective_date=date(2026, 6, 1),
            status=InvariantPackStatus.RESEARCH_PREVIEW, domain="test",
            framework_name="numeric conjunction test framework",
            transcribed_by="Test, 2026-06-01",
            clinical_source_authority="test authority", anchor_citation=cit(),
            invariants=[inv])
        lp = LoadedInvariantPack(
            name="cross_sheet/test/numconj", invariantpack=pack,
            canonical_sha256=pack.canonical_sha256(), yaml_sha256="0" * 64,
            status=InvariantPackStatus.RESEARCH_PREVIEW)
        sub = {"biomarkers": [
            {"patient_id": "P1", "centiloid": 40, "tau_suvr": 1.0},  # both -> flag
            {"patient_id": "P2", "centiloid": 40, "tau_suvr": 1.5},  # tau high -> no
            {"patient_id": "P3", "centiloid": 10, "tau_suvr": 1.0},  # CL low -> no
        ]}
        flags = [f for f in audit_cross_sheet(sub, [lp], dry_run=True).flags
                 if f.invariant_name == "numeric_conjunction_test"]
        assert len(flags) == 1
        assert flags[0].join_key_values["patient_id"] == "P1"

    def test_predicate_validation_rejects_mismatched_operator(self):
        from neurotcs.cross_sheet.schema import RowPredicate

        with pytest.raises(ValueError):
            # categorical operator with a threshold instead of value
            RowPredicate(field="x", operator="eq", threshold=1.0)
        with pytest.raises(ValueError):
            # numeric operator with a value instead of threshold
            RowPredicate(field="x", operator="ge", value="positive")
