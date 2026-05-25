"""Tests for neurotcs.clinical_ranges.schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from neurotcs.clinical_ranges.schema import (
    SCHEMA_VERSION,
    BoundType,
    Citation,
    MeasurementRange,
    RangeBound,
    RangePack,
    RangePackStatus,
    evaluate_categorical_against_valid_set,
    evaluate_value_against_bounds,
)

# ============================================================
# Citation
# ============================================================

class TestCitation:
    def test_citation_with_pmid(self):
        c = Citation(
            citation_pmid="29133356",
            citation_text="A reasonable-length anchor quote that passes min_length validation.",
        )
        assert c.citation_pmid == "29133356"
        assert c.citation_doi is None

    def test_citation_with_doi(self):
        c = Citation(
            citation_doi="10.1016/j.jalz.2018.02.018",
            citation_text="A reasonable-length anchor quote that passes min_length validation.",
        )
        assert c.citation_doi == "10.1016/j.jalz.2018.02.018"

    def test_citation_missing_all_anchors_rejected(self):
        """At least one of pmid/doi/pmid_pending+doi must be present."""
        with pytest.raises(ValidationError):
            Citation(
                citation_text="A reasonable-length anchor quote that passes min_length validation.",
            )

    def test_citation_pmid_pending_without_doi_rejected(self):
        """pmid_pending=True requires a DOI fallback."""
        with pytest.raises(ValidationError):
            Citation(
                pmid_pending=True,
                citation_text="A reasonable-length anchor quote that passes min_length validation.",
            )

    def test_citation_pmid_pending_with_doi_accepted(self):
        c = Citation(
            pmid_pending=True,
            citation_doi="10.5000/test.2026",
            citation_text="A reasonable-length anchor quote that passes min_length validation.",
        )
        assert c.pmid_pending is True

    def test_citation_text_too_short_rejected(self):
        with pytest.raises(ValidationError):
            Citation(
                citation_pmid="29133356",
                citation_text="too short",
            )

    def test_citation_frozen(self):
        c = Citation(
            citation_pmid="29133356",
            citation_text="A reasonable-length anchor quote that passes min_length validation.",
        )
        with pytest.raises(ValidationError):
            c.citation_pmid = "99999999"  # type: ignore[misc]

    def test_citation_extra_fields_rejected(self):
        """ConfigDict extra='forbid'"""
        with pytest.raises(ValidationError):
            Citation.model_validate({
                "citation_pmid": "29133356",
                "citation_text": "A reasonable-length anchor quote that passes min_length validation.",
                "unexpected_field": "foo",
            })


# ============================================================
# RangeBound
# ============================================================

def _good_citation() -> Citation:
    return Citation(
        citation_pmid="29133356",
        citation_text="A reasonable-length anchor quote that passes min_length validation.",
    )


class TestRangeBound:
    def test_simple_hard_min(self):
        b = RangeBound(
            bound_type=BoundType.HARD_MIN,
            value=50.0,
            citation=_good_citation(),
            guideline_section="Whelton 2017 §3.1",
        )
        assert b.value == 50.0
        assert b.bound_type == BoundType.HARD_MIN

    def test_invalid_bound_type_rejected(self):
        with pytest.raises(ValidationError):
            RangeBound.model_validate({
                "bound_type": "not_a_real_type",
                "value": 50.0,
                "citation": _good_citation().model_dump(),
                "guideline_section": "Whelton 2017",
            })

    def test_guideline_section_min_length(self):
        with pytest.raises(ValidationError):
            RangeBound(
                bound_type=BoundType.HARD_MIN,
                value=50.0,
                citation=_good_citation(),
                guideline_section="too",
            )


# ============================================================
# MeasurementRange
# ============================================================

class TestMeasurementRange:
    def test_numeric_with_full_bounds(self):
        m = MeasurementRange(
            name="sbp",
            unit="mmHg",
            description="Systolic blood pressure",
            bounds=[
                RangeBound(bound_type=BoundType.HARD_MIN, value=50.0,
                           citation=_good_citation(), guideline_section="A.1.1"),
                RangeBound(bound_type=BoundType.HARD_MAX, value=240.0,
                           citation=_good_citation(), guideline_section="A.1.1"),
                RangeBound(bound_type=BoundType.PLAUSIBLE_MIN, value=80.0,
                           citation=_good_citation(), guideline_section="A.1.1"),
                RangeBound(bound_type=BoundType.PLAUSIBLE_MAX, value=200.0,
                           citation=_good_citation(), guideline_section="A.1.1"),
            ],
        )
        assert m.name == "sbp"
        assert len(m.bounds) == 4

    def test_categorical_requires_valid_values(self):
        with pytest.raises(ValidationError):
            MeasurementRange(
                name="amyloid_status",
                unit="categorical",
                description="Amyloid PET status",
                measurement_kind="categorical_set",
                bounds=[
                    RangeBound(bound_type=BoundType.HARD_MIN, value=0.0,
                               citation=_good_citation(), guideline_section="A.1.1"),
                ],
                # valid_values omitted intentionally → should fail
            )

    def test_categorical_with_valid_values(self):
        m = MeasurementRange(
            name="amyloid_status",
            unit="categorical",
            description="Amyloid PET status",
            measurement_kind="categorical_set",
            valid_values=["Positive", "Negative"],
            bounds=[
                RangeBound(bound_type=BoundType.HARD_MIN, value=0.0,
                           citation=_good_citation(), guideline_section="A.1.1"),
            ],
        )
        assert m.valid_values == ["Positive", "Negative"]

    def test_inconsistent_bounds_rejected_hard_vs_plausible_min(self):
        """hard_min > plausible_min is inconsistent (plausible is supposed to be tighter)."""
        with pytest.raises(ValidationError):
            MeasurementRange(
                name="sbp",
                unit="mmHg",
                description="SBP",
                bounds=[
                    RangeBound(bound_type=BoundType.HARD_MIN, value=80.0,
                               citation=_good_citation(), guideline_section="A.1.1"),
                    RangeBound(bound_type=BoundType.PLAUSIBLE_MIN, value=50.0,
                               citation=_good_citation(), guideline_section="A.1.1"),
                ],
            )

    def test_inconsistent_bounds_rejected_hard_vs_plausible_max(self):
        """hard_max < plausible_max is inconsistent."""
        with pytest.raises(ValidationError):
            MeasurementRange(
                name="sbp",
                unit="mmHg",
                description="SBP",
                bounds=[
                    RangeBound(bound_type=BoundType.HARD_MAX, value=200.0,
                               citation=_good_citation(), guideline_section="A.1.1"),
                    RangeBound(bound_type=BoundType.PLAUSIBLE_MAX, value=240.0,
                               citation=_good_citation(), guideline_section="A.1.1"),
                ],
            )

    def test_minimum_one_bound_required(self):
        with pytest.raises(ValidationError):
            MeasurementRange(
                name="sbp",
                unit="mmHg",
                description="SBP",
                bounds=[],
            )


# ============================================================
# RangePack
# ============================================================

def _good_measurement(name: str = "sbp") -> MeasurementRange:
    return MeasurementRange(
        name=name,
        unit="mmHg",
        description="A measurement",
        bounds=[
            RangeBound(
                bound_type=BoundType.HARD_MIN,
                value=50.0,
                citation=_good_citation(),
                guideline_section="A.1.1",
            ),
        ],
    )


def _good_pack(**overrides):
    base = {
        "schema_version": SCHEMA_VERSION,
        "rangepack_id": "test/example@1.0.0",
        "pack_version": "1.0.0",
        "effective_date": "2026-05-25",
        "status": RangePackStatus.PRODUCTION,
        "domain": "test",
        "framework_name": "Test framework name",
        "transcribed_by": "Salokhiddinov M, test build",
        "clinical_source_authority": "Test authority for this test pack",
        "anchor_citation": _good_citation(),
        "measurements": [_good_measurement()],
    }
    base.update(overrides)
    return RangePack(**base)


class TestRangePack:
    def test_minimal_pack_valid(self):
        pack = _good_pack()
        assert pack.rangepack_id == "test/example@1.0.0"
        assert len(pack.measurements) == 1

    def test_unsupported_schema_rejected(self):
        with pytest.raises(ValidationError):
            _good_pack(schema_version="99.0.0")

    def test_duplicate_measurement_names_rejected(self):
        with pytest.raises(ValidationError):
            _good_pack(measurements=[_good_measurement("sbp"), _good_measurement("sbp")])

    def test_status_skeleton_blocks_audit(self):
        pack = _good_pack(status=RangePackStatus.SKELETON)
        with pytest.raises(ValueError, match="status="):
            pack.assert_usable_for_audit()

    def test_status_planned_blocks_audit(self):
        pack = _good_pack(status=RangePackStatus.PLANNED)
        with pytest.raises(ValueError):
            pack.assert_usable_for_audit()

    def test_status_production_allows_audit(self):
        pack = _good_pack(status=RangePackStatus.PRODUCTION)
        pack.assert_usable_for_audit()  # should not raise

    def test_canonical_sha256_deterministic(self):
        p1 = _good_pack()
        p2 = _good_pack()
        assert p1.canonical_sha256() == p2.canonical_sha256()

    def test_canonical_sha256_changes_on_value_change(self):
        p1 = _good_pack()
        m2 = MeasurementRange(
            name="sbp",
            unit="mmHg",
            description="A measurement",
            bounds=[RangeBound(
                bound_type=BoundType.HARD_MIN,
                value=60.0,  # changed
                citation=_good_citation(),
                guideline_section="A.1.1",
            )],
        )
        p2 = _good_pack(measurements=[m2])
        assert p1.canonical_sha256() != p2.canonical_sha256()

    def test_get_measurement(self):
        pack = _good_pack()
        m = pack.get_measurement("sbp")
        assert m is not None
        assert m.name == "sbp"
        assert pack.get_measurement("nonexistent") is None

    def test_covered_names(self):
        pack = _good_pack(measurements=[_good_measurement("a"), _good_measurement("b")])
        assert pack.covered_names() == frozenset({"a", "b"})


# ============================================================
# evaluate_value_against_bounds
# ============================================================

class TestEvaluateValue:
    def setup_method(self):
        self.bounds = [
            RangeBound(bound_type=BoundType.HARD_MIN, value=50.0,
                       citation=_good_citation(), guideline_section="A.1.1"),
            RangeBound(bound_type=BoundType.HARD_MAX, value=240.0,
                       citation=_good_citation(), guideline_section="A.1.1"),
            RangeBound(bound_type=BoundType.PLAUSIBLE_MIN, value=80.0,
                       citation=_good_citation(), guideline_section="A.1.1"),
            RangeBound(bound_type=BoundType.PLAUSIBLE_MAX, value=200.0,
                       citation=_good_citation(), guideline_section="A.1.1"),
        ]

    def test_in_range_admissible(self):
        ok, violations = evaluate_value_against_bounds(120.0, self.bounds)
        assert ok is True
        assert violations == []

    def test_below_hard_min_flagged(self):
        ok, violations = evaluate_value_against_bounds(45.0, self.bounds)
        assert ok is False
        violated_types = {bt for bt, _ in violations}
        assert BoundType.HARD_MIN in violated_types
        assert BoundType.PLAUSIBLE_MIN in violated_types  # also under plausible

    def test_above_hard_max_flagged(self):
        ok, violations = evaluate_value_against_bounds(250.0, self.bounds)
        assert ok is False
        violated_types = {bt for bt, _ in violations}
        assert BoundType.HARD_MAX in violated_types
        assert BoundType.PLAUSIBLE_MAX in violated_types

    def test_in_plausible_range_admissible(self):
        # Right at plausible_min
        ok, _ = evaluate_value_against_bounds(80.0, self.bounds)
        assert ok is True
        # Right at plausible_max
        ok, _ = evaluate_value_against_bounds(200.0, self.bounds)
        assert ok is True

    def test_below_plausible_min_only_flagged(self):
        """A value at 70 is below plausible_min but above hard_min."""
        ok, violations = evaluate_value_against_bounds(70.0, self.bounds)
        assert ok is False
        violated_types = {bt for bt, _ in violations}
        assert BoundType.PLAUSIBLE_MIN in violated_types
        assert BoundType.HARD_MIN not in violated_types


class TestEvaluateCategorical:
    def test_value_in_set(self):
        assert evaluate_categorical_against_valid_set("Positive", ["Positive", "Negative"])

    def test_value_not_in_set(self):
        assert not evaluate_categorical_against_valid_set("Maybe", ["Positive", "Negative"])

    def test_case_sensitive(self):
        assert not evaluate_categorical_against_valid_set("positive", ["Positive"])


# ============================================================
# v1.10.0-rc1 schema upgrade: CitationStrength + RESEARCH_PREVIEW
# ============================================================

class TestCitationStrengthGates:
    """The world-class evidence gate: international_consensus requires
    ≥5 endorsing_bodies AND public_url."""

    def _strong_citation(self, n_bodies: int = 5, with_url: bool = True) -> Citation:
        return Citation(
            citation_pmid="35953274",
            citation_text="A reasonable-length anchor quote that passes min_length validation.",
            public_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC9451628/" if with_url else None,
            endorsing_bodies=[f"Body_{i}" for i in range(n_bodies)],
        )

    def test_international_consensus_requires_5_bodies(self):
        """Fewer than 5 endorsing bodies must reject international_consensus."""
        from neurotcs.clinical_ranges.schema import CitationStrength
        with pytest.raises(ValidationError):
            RangeBound(
                bound_type=BoundType.HARD_MIN,
                value=50.0,
                citation=self._strong_citation(n_bodies=4, with_url=True),
                citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
                guideline_section="Test section",
            )

    def test_international_consensus_requires_public_url(self):
        """international_consensus must have public_url set."""
        from neurotcs.clinical_ranges.schema import CitationStrength
        with pytest.raises(ValidationError):
            RangeBound(
                bound_type=BoundType.HARD_MIN,
                value=50.0,
                citation=self._strong_citation(n_bodies=5, with_url=False),
                citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
                guideline_section="Test section",
            )

    def test_verbatim_requires_public_url(self):
        from neurotcs.clinical_ranges.schema import CitationStrength
        with pytest.raises(ValidationError):
            RangeBound(
                bound_type=BoundType.HARD_MIN,
                value=50.0,
                citation=self._strong_citation(n_bodies=0, with_url=False),
                citation_strength=CitationStrength.VERBATIM,
                guideline_section="Test section",
            )

    def test_international_consensus_with_5_bodies_and_url_accepted(self):
        from neurotcs.clinical_ranges.schema import CitationStrength
        b = RangeBound(
            bound_type=BoundType.HARD_MIN,
            value=50.0,
            citation=self._strong_citation(n_bodies=5, with_url=True),
            citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
            guideline_section="Test section",
        )
        assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_derived_does_not_require_url(self):
        """derived strength is the default; URL not strictly required."""
        from neurotcs.clinical_ranges.schema import CitationStrength
        b = RangeBound(
            bound_type=BoundType.HARD_MIN,
            value=50.0,
            citation=Citation(
                citation_pmid="29133356",
                citation_text="A reasonable-length anchor quote that passes min_length validation.",
            ),
            citation_strength=CitationStrength.DERIVED,
            guideline_section="Test section",
        )
        assert b.citation_strength == CitationStrength.DERIVED


class TestResearchPreviewStatus:
    """research_preview packs load but cannot be used in audit."""

    def test_research_preview_blocks_audit(self):
        pack = _good_pack(status=RangePackStatus.RESEARCH_PREVIEW)
        with pytest.raises(ValueError, match="status="):
            pack.assert_usable_for_audit()
