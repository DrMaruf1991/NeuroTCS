"""
Tests for v1.11.0a5 production promotion of cross_sheet/tool_declaration_consistency
and the empirical false-positive validation harness.

These tests verify:
- The pack is now at PRODUCTION status
- The pack's yaml_sha256 matches the v1.11.0a5 production-locked golden value
- The empirical validation script is importable and its functions are deterministic
- A small representative subset of the 1608-case corpus produces the expected
  flag counts (full 1608-case validation runs once per release via the standalone
  script in scripts/, NOT on every pytest invocation)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from neurotcs.cross_sheet import audit_cross_sheet, load_invariantpack
from neurotcs.cross_sheet.schema import InvariantPackStatus

# Locked golden yaml_sha256 for the v1.11.0a5 production-promoted pack
GOLDEN_YAML_SHA256_PROD_TOOL_DECL = (
    "6f457cb80e05ac8fc377cfa0c1b783fa25abfc76426d8c0ea5860b252766d024"
)

# Locked corpus SHA-256 from the v1.11.0a5 empirical validation
GOLDEN_CORPUS_SHA256 = (
    "ec86f00a5ad86efc95491d6b721fad4cf8089d4f19a1b4fc5c597e4c0beb6525"
)


class TestProductionPromotionStatus:

    def test_pack_loads_as_production(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp.status == InvariantPackStatus.PRODUCTION

    def test_pack_yaml_sha256_matches_v1_11_0a5_golden(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp.yaml_sha256 == GOLDEN_YAML_SHA256_PROD_TOOL_DECL

    def test_pack_still_has_4_invariants(self):
        """Production promotion is a metadata-only change. No invariant
        content changes between v1.11.0a4 and v1.11.0a5."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert len(lp.invariantpack.invariants) == 4

    def test_production_mode_accepts_dry_run_false(self):
        """Production pack does not require dry_run=True. The call must
        succeed without raising. Note: result.n_dry_run is False because
        no research_preview pack was admitted via dry-run."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        result = audit_cross_sheet(
            {"manifest": {}, "biomarkers": []}, [lp], dry_run=False
        )
        assert result.n_dry_run is False

    def test_production_mode_dry_run_true_also_works(self):
        """Production packs MUST support both dry_run modes. Note:
        result.n_dry_run is False even with dry_run=True because the
        pack is production (n_dry_run tracks whether research_preview
        was admitted, not the caller's argument)."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        result = audit_cross_sheet(
            {"manifest": {}, "biomarkers": []}, [lp], dry_run=True
        )
        # Production pack -> n_dry_run is False regardless of caller arg
        assert result.n_dry_run is False
        assert result.n_invariants_evaluated == 4

    def test_assert_usable_for_audit_does_not_raise(self):
        """Production pack must pass the fail-closed gate."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        lp.assert_usable_for_audit()  # must not raise


def _load_validation_module():
    """Import the validation script as a module so we can test its functions."""
    import sys
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "run_empirical_validation_tool_declaration.py"
    spec = importlib.util.spec_from_file_location("ev_module", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ev_module"] = module  # required for @dataclass to resolve
    spec.loader.exec_module(module)
    return module


class TestEmpiricalValidationHarness:

    def test_validation_script_imports(self):
        module = _load_validation_module()
        assert hasattr(module, "run_validation")
        assert hasattr(module, "_build_corpus")
        assert hasattr(module, "_corpus_hash")
        assert hasattr(module, "TOOL_RANGES")
        assert hasattr(module, "CORPUS_SEED")

    def test_corpus_seed_is_42(self):
        """The corpus seed is locked; do not change without bumping the
        validation revision and re-running the locked golden values."""
        module = _load_validation_module()
        assert module.CORPUS_SEED == 42

    def test_corpus_is_deterministic(self):
        """Two builds of the corpus with the same seed must produce the
        same SHA-256."""
        module = _load_validation_module()
        c1 = module._build_corpus()
        c2 = module._build_corpus()
        assert module._corpus_hash(c1) == module._corpus_hash(c2)

    def test_corpus_sha256_matches_golden(self):
        """The locked corpus SHA-256 must reproduce exactly. Drift means
        the corpus generation logic changed and the empirical validation
        results must be re-run and re-locked."""
        module = _load_validation_module()
        c = module._build_corpus()
        assert module._corpus_hash(c) == GOLDEN_CORPUS_SHA256

    def test_corpus_size_is_1608(self):
        module = _load_validation_module()
        c = module._build_corpus()
        # 4 tools x 200 good + 4 x 100 bad_below + 4 x 100 bad_above + 4 x 2 edge
        assert len(c) == 1608

    def test_corpus_balance(self):
        module = _load_validation_module()
        c = module._build_corpus()
        n_good = sum(1 for x in c if x.bucket == "good")
        n_bad_below = sum(1 for x in c if x.bucket == "bad_below")
        n_bad_above = sum(1 for x in c if x.bucket == "bad_above")
        n_edge = sum(1 for x in c if x.bucket == "edge")
        assert n_good == 800
        assert n_bad_below == 400
        assert n_bad_above == 400
        assert n_edge == 8

    def test_corpus_covers_all_four_tools(self):
        module = _load_validation_module()
        c = module._build_corpus()
        tools = {x.declared_tool for x in c}
        assert tools == {"neuroquant_5.0", "neuroreader", "icometrix", "quantib_nd"}


class TestRepresentativeCorpusSlice:
    """Verify a small representative slice of the validation corpus
    produces the expected flag counts. Full 1608-case validation runs
    only via the standalone script (scripts/run_empirical_validation_tool_declaration.py)
    to keep the unit-test suite fast."""

    def test_neuroquant_good_value_no_flag(self):
        """NeuroQuant range [2.8, 5.0], interior value 3.5 -> no flag."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert len(result.flags) == 0

    def test_neuroreader_below_range_flag(self):
        """NeuroReader range [3.5, 5.5], value 3.0 (below) -> 1 flag."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroreader"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.0}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert len(result.flags) == 1

    def test_quantib_above_range_flag(self):
        """Quantib ND range [2.8, 5.0], value 5.5 (above) -> 1 flag."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "quantib_nd"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 5.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert len(result.flags) == 1

    def test_icometrix_edge_lo_no_flag(self):
        """icometrix range [2.8, 5.0], EXACT boundary lo=2.8 -> in-range, no flag."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "icometrix"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 2.8}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert len(result.flags) == 0

    def test_icometrix_edge_hi_no_flag(self):
        """icometrix range [2.8, 5.0], EXACT boundary hi=5.0 -> in-range, no flag."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "icometrix"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 5.0}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert len(result.flags) == 0

    def test_neuroquant_edge_lo_no_flag(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 2.8}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert len(result.flags) == 0

    def test_neuroreader_edge_hi_no_flag(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroreader"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 5.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert len(result.flags) == 0


class TestProductionGateRegression:
    """Production status must not change any of the prior 4 invariants'
    semantics. These are direct regression tests against the v1.11.0a4
    behavior."""

    def test_all_4_invariants_still_evaluate(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        result = audit_cross_sheet(
            {"manifest": {"upstream_volumetry_tool": "quantib_nd"},
             "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5}]},
            [lp], dry_run=False,
        )
        assert result.n_invariants_evaluated == 4

    def test_neuroquant_invariant_range_unchanged(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.name == "neuroquant_5_0_implies_hippocampal_volume_in_normative_range"
        assert inv.condition.target_range.lo == 2.8
        assert inv.condition.target_range.hi == 5.0

    def test_neuroreader_invariant_range_unchanged(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[1]
        assert inv.condition.target_range.lo == 3.5
        assert inv.condition.target_range.hi == 5.5

    def test_icometrix_invariant_range_unchanged(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[2]
        assert inv.condition.target_range.lo == 2.8
        assert inv.condition.target_range.hi == 5.0

    def test_quantib_invariant_range_unchanged(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert inv.condition.target_range.lo == 2.8
        assert inv.condition.target_range.hi == 5.0

    def test_all_severities_still_warning(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        for inv in lp.invariantpack.invariants:
            assert inv.flag_severity == "warning"
