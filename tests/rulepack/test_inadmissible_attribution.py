"""Reproduction + guard tests for ERRATA E-2026-011: inadmissible-transition
citation over-attribution (external expert review, 2026-08).

Defect (reproduced by this file BEFORE the fix):

  ``InadmissibleTransition`` (src/neurotcs/rulepack/schema.py) carries no
  ``attribution_type`` / ``inference_rationale`` fields, while admissible
  ``Transition`` has carried them since schema v1.3.0 (ERRATA E-2026-003).
  An inadmissible rule therefore *cannot* declare that its rationale is a
  transcriber clinical inference rather than a verbatim guideline statement.

  Concrete instance: ``ad/niaaa_2018`` marks AD->MCI and AD->CN inadmissible
  citing Jack 2018 §"Clinical staging" (pp. 547-549). Jack 2018 describes the
  AD continuum but does not state a one-way CN->MCI->AD syndromal transition
  model, and dementia->MCI diagnostic reclassification is documented in
  longitudinal cohorts. The encoded inadmissibility is a defensible clinical
  inference (dementia reversion is rare under standard care, Salemme 2025)
  -- but it was presented with guideline-quote authority it does not have.

Fix under test:

  * schema v1.5.0 adds ``attribution_type`` + ``inference_rationale`` to
    ``InadmissibleTransition`` (same fail-closed validator as ``Transition``);
  * ``ad/niaaa_2018@1.4.0`` declares both AD-reversion entries
    ``clinical_inference`` with an explicit bridging rationale;
  * the new fields are provenance, never read by the scoring engine, and are
    therefore excluded from the canonical scientific SHA (E-2026-006
    partition principle) -- the pack's canonical SHA is byte-identical to
    the @1.3.0 lock, so no cohort audit_id drifts.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from neurotcs.rulepack.loader import _compute_sha256, load_rulepack
from neurotcs.rulepack.schema import (
    AttributionType,
    Citation,
    InadmissibleTransition,
)

# Canonical scientific SHA locked for ad/niaaa_2018@1.3.0 (datasheet §A,
# docs/reproducibility/ad_neurotcs_reproducibility.md). The E-2026-011
# attribution correction MUST NOT drift it.
NIAAA_2018_CANONICAL_SHA = (
    "97811e3f1a145e47393aa2568065303c594ffa20cc81a514ced027a23a81336b"
)


def _citation() -> Citation:
    return Citation(
        citation_pmid="29653606",
        citation_doi="10.1016/j.jalz.2018.02.018",
        citation_text="Jack 2018 NIA-AA Research Framework: clinical staging.",
    )


# ============================================================
# Schema-level reproduction (fails before fix: extra_forbid)
# ============================================================


def test_inadmissible_transition_accepts_clinical_inference():
    """InadmissibleTransition must be able to declare honest attribution.

    Before the fix this raises ValidationError (extra='forbid'): the schema
    cannot express 'this inadmissibility is clinical inference, not a
    verbatim guideline statement'.
    """
    t = InadmissibleTransition(
        from_state="AD",
        to_state="MCI",
        reason="Not expected to revert under standard care.",
        citation=_citation(),
        guideline_section="Jack 2018, §'Clinical staging' (pp. 547-549)",
        attribution_type="clinical_inference",
        inference_rationale=(
            "Jack 2018 does not state a one-way syndromal model; "
            "inadmissibility is a transcriber inference from reversion "
            "epidemiology."
        ),
    )
    assert t.attribution_type == AttributionType.CLINICAL_INFERENCE
    assert t.inference_rationale


def test_inadmissible_clinical_inference_requires_rationale():
    """Fail-closed parity with Transition: inference without rationale is
    rejected, so the honesty marker cannot be applied vacuously."""
    with pytest.raises(ValidationError, match="inference_rationale"):
        InadmissibleTransition(
            from_state="AD",
            to_state="CN",
            reason="Not expected.",
            citation=_citation(),
            attribution_type="clinical_inference",
        )


def test_inadmissible_default_attribution_is_guideline_quote():
    """Backward compatibility: packs that say nothing keep the strict default."""
    t = InadmissibleTransition(
        from_state="AD",
        to_state="CN",
        reason="Not expected.",
        citation=_citation(),
    )
    assert t.attribution_type == AttributionType.GUIDELINE_QUOTE
    assert t.inference_rationale is None


# ============================================================
# Pack-level reproduction (fails before fix: no attribution fields /
# guideline_quote over-attribution on the AD-reversion entries)
# ============================================================


def test_niaaa_2018_ad_reversion_entries_declare_clinical_inference():
    """The two AD-reversion inadmissible entries must carry the honest
    attribution: Jack 2018 is the informing framework, not a verbatim source
    of a one-way transition rule (external expert review, 2026-08)."""
    pack = load_rulepack("ad/niaaa_2018")
    inad = {
        (t.from_state, t.to_state): t
        for t in pack.rulepack.inadmissible_transitions
    }
    assert set(inad) == {("AD", "MCI"), ("AD", "CN")}
    for key, entry in inad.items():
        assert entry.attribution_type == AttributionType.CLINICAL_INFERENCE, (
            f"{key}: inadmissibility is not stated verbatim in Jack 2018 and "
            f"must be declared clinical_inference (ERRATA E-2026-011)"
        )
        rationale = (entry.inference_rationale or "").lower()
        assert "reclassification" in rationale, (
            f"{key}: rationale must acknowledge documented diagnostic "
            f"reclassification as a benign cause of apparent reversion"
        )
        assert "adjudication" in rationale, (
            f"{key}: rationale must state that a flag requires adjudication "
            f"and is not by itself a verdict of data error"
        )


def test_adni_clinical_stage_ad_reversions_declare_clinical_inference():
    """Same defect class, same fix: the five AD->* inadmissible entries in
    ad/adni_clinical_stage cited the identical 'Jack 2018: clinical staging
    discussion' authority. The ADNI recruitment strata are protocol
    categories, not Jack 2018 constructs."""
    pack = load_rulepack("ad/adni_clinical_stage")
    assert pack.rulepack_id == "ad/adni_clinical_stage@1.0.1"
    entries = pack.rulepack.inadmissible_transitions
    assert len(entries) == 5
    for entry in entries:
        assert entry.from_state == "AD"
        assert entry.attribution_type == AttributionType.CLINICAL_INFERENCE
        assert "adjudication" in (entry.inference_rationale or "").lower()


def test_niaaa_2024_numeric_regressions_declare_clinical_inference():
    """Same defect class, same fix: Jack 2024 Table 6 defines the numeric
    stages; the 'established dementia is not expected to revert' clause is
    transcriber inference, not Table 6 text."""
    pack = load_rulepack("ad/niaaa_2024_clinical_numeric")
    assert pack.rulepack_id == "ad/niaaa_2024_clinical_numeric@1.0.1"
    entries = pack.rulepack.inadmissible_transitions
    assert len(entries) == 15
    for entry in entries:
        assert entry.attribution_type == AttributionType.CLINICAL_INFERENCE
        assert "adjudication" in (entry.inference_rationale or "").lower()


# Canonical scientific SHAs locked at the pre-E-2026-011 versions of the two
# additional corrected packs (computed from git HEAD before the correction;
# verified IDENTICAL after). Locking them here makes the no-drift property
# regression-tested for all three corrected packs.
ADNI_CLINICAL_STAGE_CANONICAL_SHA_PREFIX = "0f032caf1e48fb61"
NIAAA_2024_NUMERIC_CANONICAL_SHA_PREFIX = "a7384bd8c34230c9"


def test_corrected_packs_canonical_sha_unchanged():
    for name, prefix in [
        ("ad/adni_clinical_stage", ADNI_CLINICAL_STAGE_CANONICAL_SHA_PREFIX),
        ("ad/niaaa_2024_clinical_numeric", NIAAA_2024_NUMERIC_CANONICAL_SHA_PREFIX),
    ]:
        pack = load_rulepack(name)
        assert pack.sha256.startswith(prefix), (
            f"{name}: canonical SHA drifted -- the E-2026-011 attribution "
            f"correction must be provenance-only"
        )


def test_niaaa_2018_version_bumped_for_attribution_correction():
    """Transcription-audit policy: an attribution discrepancy triggers a
    rule-pack version bump (docs/transcription_audit/ad_niaaa_2018.md)."""
    pack = load_rulepack("ad/niaaa_2018")
    assert pack.rulepack_id == "ad/niaaa_2018@1.4.0"
    assert pack.rulepack.ruleset_version == "1.4.0"


# ============================================================
# Canonical-SHA continuity guards (must hold before AND after the fix)
# ============================================================


def test_niaaa_2018_canonical_sha_unchanged_by_attribution_correction():
    """The attribution fields are provenance, not science: the canonical
    scientific SHA must remain byte-identical to the @1.3.0 lock, so every
    locked cohort audit_id (four-cohort triangulation) remains valid."""
    pack = load_rulepack("ad/niaaa_2018")
    assert pack.sha256 == NIAAA_2018_CANONICAL_SHA


def test_inadmissible_attribution_fields_never_drift_canonical_sha():
    """Two-directional partition proof for the new fields (extends
    tests/rulepack/test_canonical_serialization_partition.py):

      * flipping attribution_type / inference_rationale on an inadmissible
        entry does NOT change the canonical SHA;
      * changing the entry's science (the state pair) DOES.
    """
    pack = load_rulepack("ad/niaaa_2018")
    rp = pack.rulepack
    base_sha = _compute_sha256(rp)

    entry = rp.inadmissible_transitions[0]

    flipped_attr = (
        AttributionType.GUIDELINE_QUOTE
        if entry.attribution_type == AttributionType.CLINICAL_INFERENCE
        else AttributionType.CLINICAL_INFERENCE
    )
    mutated_provenance = rp.model_copy(
        update={
            "inadmissible_transitions": [
                entry.model_copy(
                    update={
                        "attribution_type": flipped_attr,
                        "inference_rationale": "a completely different rationale",
                    }
                ),
                *rp.inadmissible_transitions[1:],
            ]
        }
    )
    assert _compute_sha256(mutated_provenance) == base_sha, (
        "attribution provenance on inadmissible transitions must be excluded "
        "from the canonical scientific SHA (E-2026-006 partition principle)"
    )

    mutated_science = rp.model_copy(
        update={
            "inadmissible_transitions": [
                entry.model_copy(update={"to_state": "CN_XXX"}),
                *rp.inadmissible_transitions[1:],
            ]
        }
    )
    assert _compute_sha256(mutated_science) != base_sha, (
        "changing the inadmissible state pair is a scientific change and "
        "MUST drift the canonical SHA"
    )
