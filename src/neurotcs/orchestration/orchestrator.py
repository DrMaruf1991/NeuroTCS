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


def _tier_for_flag(flag: dict[str, Any]) -> str:
    """Classify a range-pack flag into a severity tier (Invariant B)."""
    sev = str(flag.get("flag_severity", "")).lower()
    bound = str(flag.get("bound_type", "")).lower()
    if sev in ("hard", "invalid_category") or bound.startswith("hard") or "invalid" in sev:
        return TIER_IMPOSSIBLE
    # "plausible_*" bounds that encode diagnostic/clinical thresholds are
    # informational, not data errors; genuine physiological-range bounds are
    # implausible. We treat plausible-bound firing as informational by default
    # because that is the dominant (and noisiest) case, and surface the
    # impossible tier first.
    if "plausible" in bound or sev == "plausible":
        return TIER_INFORMATIONAL
    return TIER_IMPLAUSIBLE


def run_full_audit(
    submission: dict[str, Any],
    *,
    disease_domain: str | None = "alzheimers",
    skip_layers: dict[str, str] | None = None,
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
                         "flag_severity")}
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
                fl.append({"invariant": f.invariant_name,
                           "join_key": f.join_key_values,
                           "reason": f.flag_reason, "tier": TIER_IMPOSSIBLE})
                severity[TIER_IMPOSSIBLE] += 1
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

    # ---- completeness check (Invariant A) ----
    ran_layers = [layer.layer for layer in layers if layer.ran]
    skipped = {layer.layer: (layer.skipped_reason or "")
               for layer in layers if not layer.ran}
    unrecorded = [layer for layer, reason in skipped.items() if not reason]

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

    if unrecorded:
        return OrchestratorResult(
            orchestrator_audit_id="",
            complete=False,
            refusal_reason=(
                f"REFUSED (fail-closed): applicable layer(s) {unrecorded} were "
                f"skipped without a recorded reason. A NeuroTCS result must be "
                f"complete-or-refuse: a clean result must mean 'checked and "
                f"clean', never 'never checked'. Provide skip_layers={{layer: "
                f"reason}} to deliberately and transparently skip a layer."),
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
