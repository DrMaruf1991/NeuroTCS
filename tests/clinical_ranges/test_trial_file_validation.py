"""
Gold-standard end-to-end test: run Layer 2 against the trial file.

In v1.10.0-rc1 (the world-class restructure), only `ad/aria_safety` is
status=production. The original 6 v1.10.0-draft packs are demoted to
research_preview pending their own citation-trace upgrade.

The trial Excel file does not contain ARIA-specific columns (it pre-dates
the ARIA monitoring schema), so this test is currently a sanity test that:
  - the production pack loads
  - the audit framework runs without errors when no measurement matches
  - the multi-pack convenience function correctly skips research_preview packs

Skips if the trial Excel is not available at the expected path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neurotcs.clinical_ranges import (
    audit_clinical_ranges,
    list_rangepacks,
    load_rangepack,
)
from neurotcs.clinical_ranges.adapters import trial_excel_to_measurements

# Trial file lives outside the repo (uploaded by the user)
_TRIAL_XLSX = Path("/mnt/user-data/uploads/Trial_AD_MCI_AntiAmyloid_v2.xlsx")


pytestmark = pytest.mark.skipif(
    not _TRIAL_XLSX.exists(),
    reason="Trial Excel file not present at expected path; this test is a"
           " gold-standard check that runs when the file is available."
)


@pytest.fixture(scope="module")
def trial_long_format():
    """Adapter output cached for all tests in this module."""
    return trial_excel_to_measurements(_TRIAL_XLSX)


@pytest.fixture(scope="module")
def aria_pack():
    """Only production pack in v1.10.0-rc1."""
    return load_rangepack("ad/aria_safety")


class TestTrialFileAdapter:
    """The adapter must still produce a valid long-format DataFrame even
    though the production pack doesn't currently cover any of these columns."""

    def test_adapter_produces_long_format(self, trial_long_format):
        assert len(trial_long_format) > 0
        for col in ("patient_id", "visit_id", "measurement_name", "value", "unit"):
            assert col in trial_long_format.columns


class TestProductionPackOnTrialFile:
    """Run the production ad/aria_safety pack against the trial file.

    The trial file pre-dates the ARIA reporting schema, so no measurements
    will match — they all land in uncovered, which is the correct
    fail-closed behavior."""

    def test_audit_runs_without_error(self, trial_long_format, aria_pack):
        result = audit_clinical_ranges(trial_long_format, aria_pack)
        assert result.flag_id  # deterministic flag_id produced
        # The trial file has no ARIA-coded measurements, so everything is uncovered
        assert result.n_measurements_covered == 0
        assert result.n_measurements_uncovered > 0
        assert result.n_flagged == 0

    def test_audit_is_deterministic(self, trial_long_format, aria_pack):
        r1 = audit_clinical_ranges(trial_long_format, aria_pack)
        r2 = audit_clinical_ranges(trial_long_format, aria_pack)
        assert r1.flag_id == r2.flag_id


class TestResearchPreviewAndDeprecatedPacksRejectAudit:
    """In v1.10.2: 1 research_preview + 6 deprecated packs must all refuse audit.
    The framework refuses to silently emit flags from a non-production pack."""

    @pytest.mark.parametrize("pack_name", [
        # Research preview (still valid for future upgrade)
        "mri_volumetrics/freesurfer_extended",
        # Deprecated (superseded or out-of-scope)
        "vital_signs/standard",
        "csf_biomarkers/aa_2024",
        "plasma_biomarkers/aa_2024",
        "pet_amyloid/centiloid",
        "genetics/apoe_valid_genotypes",
        "mri_volumetrics/freesurfer",  # v1.10.2 deprecation
    ])
    def test_non_production_pack_refuses_audit(self, trial_long_format, pack_name):
        lp = load_rangepack(pack_name)
        with pytest.raises(ValueError):
            audit_clinical_ranges(trial_long_format, lp)


class TestPacksListAccurate:
    """Tracks the current production / research_preview / deprecated roster.

    v1.10.2: 6 production + 1 research_preview + 6 deprecated.
    v1.13.0: +1 production (wmh_fazekas_consensus) -> 7/1/6.
    v1.15.0: +1 production (tau_pet/tau_consensus) + 1 preview
             (tau_pet/tau_research_preview) -> 8/2/6.
    v1.16.0: +1 production (fdg_pet/fdg_consensus) -> 9/2/6.
    v1.17.0: +6 production + 2 preview (batch Tier 2 closure) -> 15/4/6.
    v1.22.0: +1 production (NfL) -> 16/4/6. (Demographic plausibility
    moved to the input-contract data-integrity layer.)
    """

    def test_exactly_sixteen_production_packs(self):
        packs = list_rangepacks()
        production = [p for p in packs if p.get("status") == "production"]
        assert len(production) == 16
        names = {p["name"] for p in production}
        assert names == {
            "ad/aria_safety",
            "pet_amyloid/centiloid_consensus",
            "genetics/apoe_consensus",
            "csf_biomarkers/csf_amyloid_consensus",
            "plasma_biomarkers/plasma_amyloid_consensus",
            "mri_volumetrics/structural_volumetry_consensus",  # NEW v1.10.2
            "mri_volumetrics/wmh_fazekas_consensus",  # NEW v1.13.0 / v1.15.1
            "tau_pet/tau_consensus",  # NEW v1.15.0
            "fdg_pet/fdg_consensus",  # NEW v1.16.0
            # v1.17.0 batch Tier 2 closure (6 new production packs)
            "cognitive_scales/cdr_mmse_moca_consensus",
            "cognitive_scales/adas_cog_iadrs_consensus",
            "cognitive_scales/npiq_consensus",
            "olfactory/upsit_consensus",
            "mri_volumetrics/microbleeds_boston_consensus",
            "csf_biomarkers/csf_tau_consensus",
            # v1.22.0 (NfL plasma biomarker plausibility pack)
            "plasma_biomarkers/nfl_consensus",
        }

    def test_four_research_preview_packs(self):
        """v1.17.0: research_preview roster includes mri_volumetrics/
        freesurfer_extended (v1.10.2), tau_pet/tau_research_preview
        (v1.15.0), csf_biomarkers/csf_ptau231_research_preview (v1.17.0),
        and genetics/trem2_research_preview (v1.17.0). The latter two
        ship as research_preview (not production) because they lack FDA
        clearance + are not in AA-2024 Table 7 + have no clinical-grade
        actionable threshold — same world-class evidence honesty
        discipline as v1.13.1 CSF p-tau217 and v1.15.2 NfL/GFAP
        downgrades."""
        packs = list_rangepacks()
        preview = [p for p in packs if p.get("status") == "research_preview"]
        assert len(preview) == 4
        names = {p["name"] for p in preview}
        assert names == {
            "mri_volumetrics/freesurfer_extended",
            "tau_pet/tau_research_preview",
            "csf_biomarkers/csf_ptau231_research_preview",
            "genetics/trem2_research_preview",
        }

    def test_six_deprecated_packs(self):
        packs = list_rangepacks()
        deprecated = [p for p in packs if p.get("status") == "deprecated"]
        assert len(deprecated) == 6
        names = {p["name"] for p in deprecated}
        assert names == {
            "vital_signs/standard",
            "csf_biomarkers/aa_2024",
            "plasma_biomarkers/aa_2024",
            "genetics/apoe_valid_genotypes",
            "pet_amyloid/centiloid",
            "mri_volumetrics/freesurfer",  # NEW v1.10.2
        }
