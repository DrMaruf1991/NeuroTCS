"""neurotcs.orchestration.orchestrator -- the fail-closed audit spine.

This module makes the failure that motivated it structurally impossible:
a careful operator running NeuroTCS produced a clean-looking result that had
silently skipped the cross-sheet layer, then mislabeled that territory as
"out of scope." The fix is not "remember to run every layer" -- it is to
make completeness a property of the code, not the operator.

run_full_audit(submission):
  * auto-discovers every layer applicable to the input,
  * runs all applicable layers,
  * REFUSES to emit a final orchestrator audit_id if any applicable layer was
    skipped without an explicitly recorded reason (Invariant A: completeness),
  * emits a coverage manifest -- which layers ran, which packs+SHAs applied,
    which columns were consumed vs ignored, which layers were skipped and why
    (Invariant C: transparency),
  * computes an orchestrator-level deterministic audit_id that hashes the
    coverage manifest together with every sub-layer audit_id. This id is
    ADDITIVE: it does not alter any existing per-layer audit_id (so locked
    ADNI/OASIS-3/MIRIAD ids are untouched), but two runs that checked
    different things produce different orchestrator ids -- a partial audit is
    cryptographically distinguishable from a complete one, forever.

The orchestrator emits no staging score on mismatched vocabulary (Invariant B
is enforced via orchestration.vocabulary).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from neurotcs.audit_core.audit import audit
from neurotcs.audit_core.trajectory import trajectories_from_dataframe
from neurotcs.orchestration.vocabulary import (
    VocabularyMismatchError,
    select_rulepack_or_refuse,
)
from neurotcs.rulepack.loader import load_rulepack

ORCHESTRATOR_VERSION = "1.0.0"

# Severity tiers for range/biomarker flags (Invariant B reporting): the
# 1,070-flag run drowned 10 real data errors under ~1,000 clinical-threshold
# crossings. The orchestrator sorts flags so the reader leads with truth.
TIER_IMPOSSIBLE = "impossible"        # hard-bound / invalid-category: data-integrity errors
TIER_IMPLAUSIBLE = "implausible"      # outside physiological range, not impossible
TIER_INFORMATIONAL = "informational"  # value crosses a clinical/diagnostic threshold; not an error


@dataclass
class LayerResult:
    layer: str
    ran: bool
    skipped_reason: str | None = None
    audit_id: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    flags: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CoverageManifest:
    orchestrator_version: str
    layers_run: list[str]
    layers_skipped: dict[str, str]            # layer -> recorded reason
    packs_applied: dict[str, str]             # layer/pack -> sha256
    columns_consumed: dict[str, list[str]]    # sheet -> columns the audit read
    columns_ignored: dict[str, list[str]]     # sheet -> columns no layer audited
    sub_audit_ids: dict[str, str]             # layer -> per-layer audit_id


@dataclass
class OrchestratorResult:
    orchestrator_audit_id: str
    complete: bool
    refusal_reason: str | None
    manifest: CoverageManifest
    layers: list[LayerResult]
    severity_summary: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "orchestrator_audit_id": self.orchestrator_audit_id,
            "complete": self.complete,
            "refusal_reason": self.refusal_reason,
            "manifest": asdict(self.manifest),
            "layers": [asdict(layer) for layer in self.layers],
            "severity_summary": self.severity_summary,
        }


class IncompleteAuditError(RuntimeError):
    """Raised when an applicable layer was skipped without a recorded reason."""


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _compute_orchestrator_id(manifest: CoverageManifest) -> str:
    """Deterministic SHA-256 over the coverage manifest + all sub-audit_ids.

    Hashing the manifest (what ran, what was skipped, which columns were
    consumed/ignored, pack SHAs) means a partial run and a complete run can
    never collide -- the whole point of Invariant A + C.
    """
    h = hashlib.sha256()
    h.update(ORCHESTRATOR_VERSION.encode())
    h.update(_canonical(asdict(manifest)).encode())
    return h.hexdigest()


_CROSS_SHEET_SEVERITY_TIER = {
    "error": TIER_IMPOSSIBLE,        # biologically impossible internal contradiction
    "warning": TIER_IMPLAUSIBLE,     # discordance/monotonicity break flagged for review
    "info": TIER_INFORMATIONAL,      # advisory note
    "informational": TIER_INFORMATIONAL,
}


def _tier_for_cross_sheet_flag(f: Any) -> str:
    """Map a cross-sheet invariant flag to a severity tier by its DECLARED severity.

    Previously every cross-sheet flag was force-tiered TIER_IMPOSSIBLE. That
    promoted invariants the pack author declared as `warning` (e.g. biomarker
    discordances, trajectory-monotonicity breaks -- 'flag for human review',
    NOT 'biologically impossible') up into the impossible tier, drowning the
    handful of true `error`-severity contradictions. The invariant YAML is the
    source of truth for severity; the orchestrator now honors it. Unknown /
    missing severity falls back to TIER_IMPOSSIBLE (fail-safe: never silently
    downgrade an unclassified contradiction).
    """
    sev = str(getattr(f, "severity", "") or "").strip().lower()
    return _CROSS_SHEET_SEVERITY_TIER.get(sev, TIER_IMPOSSIBLE)


def _tier_for_flag(flag: dict[str, Any]) -> str:
    """Classify a range-pack flag into a severity tier (Invariant B).

    - hard bounds / invalid category -> impossible.
    - plausible bounds -> implausible IF the bound is declared as a
      physiological-envelope bound (bound_semantic == 'physiological_envelope'),
      else informational (the default for diagnostic/clinical-threshold bounds,
      whose crossing is expected in a real cohort and is not an error).

    The semantic distinction is declared by the range pack (a plausible_max on a
    concentration ceiling is an implausibility; a plausible bound at a
    diagnostic cutpoint is informational). Absent the declaration we default to
    informational to preserve the auditor's zero-false-alarm discipline.
    """
    sev = str(flag.get("flag_severity", "")).lower()
    bound = str(flag.get("bound_type", "")).lower()
    if sev in ("hard", "invalid_category") or bound.startswith("hard") or "invalid" in sev:
        return TIER_IMPOSSIBLE
    if "plausible" in bound or sev == "plausible":
        semantic = str(flag.get("bound_semantic", "")).lower()
        if semantic == "physiological_envelope":
            return TIER_IMPLAUSIBLE
        return TIER_INFORMATIONAL
    return TIER_IMPLAUSIBLE


def run_full_audit(
    submission: dict[str, Any],
    *,
    disease_domain: str | None = "alzheimers",
    skip_layers: dict[str, str] | None = None,
    expected_layers: list[str] | None = None,
    bootstrap_B: int = 10000,
    seed: int = 42,
) -> OrchestratorResult:
    """Run every applicable NeuroTCS layer, fail-closed.

    Parameters
    ----------
    submission : dict
        Keys (all optional; a layer is "applicable" iff its inputs are present):
          - "clinical": DataFrame[subject_id, visit, visit_date, state]
          - "biological": DataFrame[subject_id, visit, visit_date, state]
          - "ranges": list of (rangepack_name, measurements_df) for Layer 2
          - "cross_sheet": (submission_dict, [invariant_pack_names]) for Layer 3
          - "input_contract": Path to a v1.2 submission dir for the contract layer
        Plus optional "columns_present": dict[sheet -> list[str]] so the manifest
        can report consumed-vs-ignored columns honestly.
    skip_layers : dict[layer -> reason]
        Explicit, recorded reasons for deliberately skipping an applicable
        layer. A layer skipped WITHOUT a reason here triggers refusal.

    Returns OrchestratorResult. If any applicable layer was skipped without a
    recorded reason, complete=False and orchestrator_audit_id is empty.
    """
    skip_layers = skip_layers or {}
    layers: list[LayerResult] = []
    packs_applied: dict[str, str] = {}
    sub_ids: dict[str, str] = {}
    severity = {TIER_IMPOSSIBLE: 0, TIER_IMPLAUSIBLE: 0, TIER_INFORMATIONAL: 0}

    # ---- discover applicable layers ----
    applicable: list[str] = []
    if isinstance(submission.get("clinical"), pd.DataFrame):
        applicable.append("staging_clinical")
    if isinstance(submission.get("biological"), pd.DataFrame):
        applicable.append("staging_biological")
    if submission.get("ranges"):
        applicable.append("ranges")
    if submission.get("cross_sheet"):
        applicable.append("cross_sheet")
    if submission.get("input_contract"):
        applicable.append("input_contract")
    if submission.get("data_integrity"):
        applicable.append("data_integrity")

    # ---- run each applicable layer (or record an explicit skip) ----
    for layer in applicable:
        if layer in skip_layers:
            layers.append(LayerResult(layer=layer, ran=False,
                                      skipped_reason=skip_layers[layer]))
            continue

        if layer in ("staging_clinical", "staging_biological"):
            df = submission["clinical" if layer == "staging_clinical" else "biological"]
            states = df["state"].tolist()
            try:
                pack_name, vm = select_rulepack_or_refuse(
                    states, disease_domain=disease_domain)
            except VocabularyMismatchError as e:
                # fail-closed: refuse to score this axis, but RECORD it as a
                # skip-with-reason so the orchestrator can still finalize the
                # other layers honestly.
                layers.append(LayerResult(layer=layer, ran=False,
                                          skipped_reason=f"vocabulary_mismatch: {e}"))
                continue
            lp = load_rulepack(pack_name)
            trajs = trajectories_from_dataframe(
                df, patient_id_col="subject_id", visit_date_col="visit_date",
                state_col="state", skip_invalid=False)
            res = audit(trajs, lp, bootstrap_B=bootstrap_B, seed=seed,
                        return_per_transition=True)
            d = res.to_dict()
            packs_applied[f"{layer}:{pack_name}"] = d["rulepack"]["sha256"]
            sub_ids[layer] = d["audit_id"]
            fl = []
            pt = res.per_transition
            for i in range(len(pt.flags)):
                if pt.flags[i]:
                    fl.append({"subject_id": pt.patient_ids[i],
                               "from": pt.from_states[i], "to": pt.to_states[i],
                               "delta_days": float(pt.delta_days[i]),
                               "tier": TIER_IMPOSSIBLE})
                    severity[TIER_IMPOSSIBLE] += 1
            layers.append(LayerResult(
                layer=layer, ran=True, audit_id=d["audit_id"],
                summary={"pack": pack_name, "ctcs": d["metrics"]["ctcs"]["point"],
                         "ctcs_ci_95_low": d["metrics"]["ctcs"].get("ci_95_low"),
                         "ctcs_ci_95_high": d["metrics"]["ctcs"].get("ci_95_high"),
                         "ctcs_ci_method": d["metrics"]["ctcs"].get("ci_method"),
                         "ctcs_huber": d["metrics"]["ctcs"].get("huber"),
                         "bootstrap_B": d["metrics"]["ctcs"].get("B"),
                         "n_transitions": d["cohort"]["n_transitions"],
                         "n_flagged": d["cohort"]["n_flagged"],
                         "vocabulary_coverage": vm.coverage_fraction,
                         "contamination_tokens": list(vm.unmatched)},
                flags=fl))

        elif layer == "ranges":
            from neurotcs.clinical_ranges import audit_clinical_ranges, load_rangepack
            ran_any = False
            all_fl: list[dict[str, Any]] = []
            for pack_name, meas_df in submission["ranges"]:
                rp = load_rangepack(pack_name)
                rres = audit_clinical_ranges(meas_df, rp)
                packs_applied[f"ranges:{pack_name}"] = rres.rangepack_sha256
                ran_any = True
                for f in (rres.flags or []):
                    fd = f if isinstance(f, dict) else {
                        k: getattr(f, k) for k in
                        ("patient_id", "visit_id", "measurement_name",
                         "observed_value", "bound_type", "bound_value",
                         "flag_severity", "bound_semantic")}
                    tier = _tier_for_flag(fd)
                    fd["tier"] = tier
                    severity[tier] += 1
                    all_fl.append(fd)
            layers.append(LayerResult(
                layer="ranges", ran=ran_any,
                summary={"n_packs": len(submission["ranges"]),
                         "n_flags_total": len(all_fl)},
                flags=all_fl))

        elif layer == "cross_sheet":
            from neurotcs.cross_sheet import audit_cross_sheet, load_invariantpack
            cs_sub, pack_names = submission["cross_sheet"]
            packs = [load_invariantpack(n) for n in pack_names]
            cres = audit_cross_sheet(cs_sub, packs, dry_run=False)
            for n, p in zip(pack_names, packs, strict=False):
                packs_applied[f"cross_sheet:{n}"] = getattr(
                    p, "sha256", getattr(p, "invariantpack_sha256", ""))
            fl = []
            for f in cres.flags:
                tier = _tier_for_cross_sheet_flag(f)
                fl.append({"invariant": f.invariant_name,
                           "join_key": f.join_key_values,
                           "reason": f.flag_reason,
                           "severity": getattr(f, "severity", None),
                           "tier": tier})
                severity[tier] += 1
            layers.append(LayerResult(
                layer="cross_sheet", ran=True,
                summary={"n_packs": len(pack_names), "n_flags": len(cres.flags)},
                flags=fl))

        elif layer == "input_contract":
            from neurotcs.input_contract.v1_2.validate import validate_submission
            rep = validate_submission(submission["input_contract"])
            fl = [{"code": e.code, "location": e.location,
                   "message": e.message, "tier": TIER_IMPOSSIBLE}
                  for e in rep.errors]
            for _ in fl:
                severity[TIER_IMPOSSIBLE] += 1
            layers.append(LayerResult(
                layer="input_contract", ran=True,
                summary={"n_errors": len(rep.errors),
                         "n_warnings": len(rep.warnings)},
                flags=fl))

        elif layer == "data_integrity":
            # Universal Layer-1 integrity flags were pre-computed by the caller
            # (the resolver runs over raw sheets, which the orchestrator does
            # not hold). submission["data_integrity"] is the flag list.
            di_flags = submission["data_integrity"]
            fl = []
            for f in di_flags:
                tier = f.get("tier", TIER_IMPOSSIBLE)
                if tier not in severity:
                    tier = TIER_IMPOSSIBLE
                severity[tier] += 1
                fl.append(f)
            layers.append(LayerResult(
                layer="data_integrity", ran=True,
                summary={"n_flags": len(fl)},
                flags=fl))

    # ---- completeness check (Invariant A) ----
    ran_layers = [layer.layer for layer in layers if layer.ran]
    skipped = {layer.layer: (layer.skipped_reason or "")
               for layer in layers if not layer.ran}
    unrecorded = [layer for layer, reason in skipped.items() if not reason]

    # ---- structural completeness guard (closes the circular hole) ----
    # Historically a layer was "applicable" iff its submission key was present;
    # so a layer whose key was never populated (a wiring omission) was silently
    # deemed not-applicable and the completeness check passed vacuously. The
    # caller now declares the layers it EXPECTED to be offered (expected_layers).
    # Any expected layer that is neither applicable nor explicitly skipped was
    # silently dropped -> refuse. This makes a wiring omission fail loudly
    # instead of producing a falsely-clean "complete" result.
    silently_dropped: list[str] = []
    if expected_layers:
        offered = set(applicable) | set((skip_layers or {}).keys())
        silently_dropped = [layer_name for layer_name in expected_layers
                            if layer_name not in offered]

    cols_present = submission.get("columns_present", {})
    cols_consumed = submission.get("columns_consumed", {})
    cols_ignored = {sheet: [c for c in cols if c not in cols_consumed.get(sheet, [])]
                    for sheet, cols in cols_present.items()}

    manifest = CoverageManifest(
        orchestrator_version=ORCHESTRATOR_VERSION,
        layers_run=ran_layers,
        layers_skipped=skipped,
        packs_applied=packs_applied,
        columns_consumed=cols_consumed,
        columns_ignored=cols_ignored,
        sub_audit_ids=sub_ids,
    )

    if unrecorded or silently_dropped:
        reason_parts = []
        if unrecorded:
            reason_parts.append(
                f"applicable layer(s) {unrecorded} were skipped without a "
                f"recorded reason")
        if silently_dropped:
            reason_parts.append(
                f"expected layer(s) {silently_dropped} were never wired "
                f"(no supporting input and no explicit skip) -- a silent "
                f"omission, not a deliberate skip")
        return OrchestratorResult(
            orchestrator_audit_id="",
            complete=False,
            refusal_reason=(
                "REFUSED (fail-closed): " + "; ".join(reason_parts) + ". A "
                "NeuroTCS result must be complete-or-refuse: a clean result "
                "must mean 'checked and clean', never 'never checked'. Provide "
                "skip_layers={layer: reason} to deliberately and transparently "
                "skip a layer."),
            manifest=manifest,
            layers=layers,
            severity_summary=severity,
        )

    return OrchestratorResult(
        orchestrator_audit_id=_compute_orchestrator_id(manifest),
        complete=True,
        refusal_reason=None,
        manifest=manifest,
        layers=layers,
        severity_summary=severity,
    )
