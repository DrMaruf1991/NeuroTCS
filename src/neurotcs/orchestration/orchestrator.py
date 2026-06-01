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
from neurotcs.orchestration.differential_registry import (
    AD_COMORBIDITY,
    NON_AD_PRIMARY,
    classify_token,
)
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


def _partition_cohort_by_frame(
    df: pd.DataFrame,
) -> dict[str, Any]:
    """Partition a clinical cohort per-subject into diagnostic frames.

    The cohort is NOT a monolith. Each subject is classified by the tokens in
    its ``state`` column across visits:

      * ad_frame        -- every state is an AD-trajectory token (no recognized
                           non-AD primary token, no comorbidity token). Staged
                           normally under an AD rule pack.
      * comorbidity     -- AD-trajectory states PLUS one or more AD_COMORBIDITY
                           tokens (e.g. CVD, WMH). The comorbidity tokens are
                           STRIPPED from the staged trajectory and recorded as
                           annotations; the subject's AD states are staged
                           normally. (Q2 decision: comorbidity stratifier on the
                           AD axis.)
      * mixed_primary   -- AD-trajectory states AND >=1 NON_AD_PRIMARY token
                           (e.g. a subject recorded MCI then DLB). The AD states
                           are staged (partial frame); non-monotonic / reversion
                           flags for these subjects are downgraded to REVIEW tier
                           because a non-AD component can legitimately explain a
                           non-monotonic course. (Q1 decision.)
      * non_ad          -- every non-trajectory token is a recognized
                           NON_AD_PRIMARY token (DLB/FTD/VaD/PDD/NPH) and there
                           are no AD-trajectory states. Partitioned OUT and
                           reported as out-of-AD-scope; NOT staged (AD rules do
                           not govern these; e.g. DLB fluctuation would
                           false-flag).
      * unrecognized    -- contains a token that is neither an AD-trajectory
                           state nor a recognized registry token. Fail-closed:
                           the subject cannot be staged or honestly partitioned,
                           so the whole layer still refuses (never a silent pass).

    A token is treated as an "AD-trajectory state" if it is NOT in the
    differential registry (registry tokens are exactly the non-AD/comorbidity
    set; AD vocabularies like CN/MCI/AD/EMCI/... return None from
    classify_token). The actual AD-pack vocabulary match still happens
    downstream via select_rulepack_or_refuse on the ad_frame partition only.

    Returns a dict with keys: ad_subject_ids, comorbidity (subj -> [annotation
    canon]), mixed_primary (subj -> [non_ad canon]), non_ad (subj -> [non_ad
    canon]), unrecognized (subj -> [unknown tokens]), ad_states (the states for
    the stageable AD partition, comorbidity tokens stripped). All collections
    are deterministically ordered (subjects sorted).
    """
    by_subject: dict[str, list[str]] = {}
    for sid, state in zip(df["subject_id"].tolist(), df["state"].tolist(), strict=False):
        by_subject.setdefault(str(sid), []).append(state)

    ad_subject_ids: list[str] = []
    comorbidity: dict[str, list[str]] = {}
    mixed_primary: dict[str, list[str]] = {}
    non_ad: dict[str, list[str]] = {}
    unrecognized: dict[str, list[str]] = {}

    for sid in sorted(by_subject):
        states = by_subject[sid]
        ad_states = []          # tokens NOT in the registry (candidate AD states)
        nonad_canons = []       # recognized NON_AD_PRIMARY canonicals
        comorb_canons = []      # recognized AD_COMORBIDITY canonicals
        unknown: list[str] = []  # genuinely unrecognized (handled fail-closed below)
        for st in states:
            entry = classify_token(st)
            if entry is None:
                # Not in the differential registry -> candidate AD-trajectory
                # state (the AD-pack vocabulary check happens downstream).
                ad_states.append(st)
            elif entry.kind == NON_AD_PRIMARY:
                nonad_canons.append(entry.canonical)
            elif entry.kind == AD_COMORBIDITY:
                comorb_canons.append(entry.canonical)

        has_ad = len(ad_states) > 0
        has_nonad = len(nonad_canons) > 0
        has_comorb = len(comorb_canons) > 0

        # Dedup canonicals deterministically (preserve first-seen order).
        nonad_u = list(dict.fromkeys(nonad_canons))
        comorb_u = list(dict.fromkeys(comorb_canons))

        if has_ad and has_nonad:
            mixed_primary[sid] = nonad_u
            ad_subject_ids.append(sid)          # AD component IS staged (partial)
            if has_comorb:
                comorbidity[sid] = comorb_u
        elif has_ad and has_comorb:
            comorbidity[sid] = comorb_u
            ad_subject_ids.append(sid)
        elif has_ad:
            ad_subject_ids.append(sid)
        elif has_nonad:
            # No AD states at all -> recognized non-AD primary subject.
            non_ad[sid] = nonad_u
            if has_comorb:
                # comorbidity tokens alone on a non-AD subject are noted there
                non_ad[sid] = nonad_u + comorb_u
        else:
            # Only comorbidity tokens and nothing else, or empty -> we cannot
            # honestly stage or partition. Fail-closed.
            unknown = [str(s) for s in states]
            unrecognized[sid] = unknown

    # Build the stageable AD partition's rows (comorbidity tokens stripped so
    # they never enter the trajectory as a fake "state").
    ad_set = set(ad_subject_ids)
    mask = []
    for sid, st in zip(df["subject_id"].tolist(), df["state"].tolist(), strict=False):
        keep = str(sid) in ad_set and classify_token(st) is None
        mask.append(keep)
    ad_df = df.loc[mask].copy()

    return {
        "ad_subject_ids": ad_subject_ids,
        "ad_df": ad_df,
        "comorbidity": comorbidity,
        "mixed_primary": mixed_primary,
        "non_ad": non_ad,
        "unrecognized": unrecognized,
    }


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

            # ---- per-subject diagnostic partitioning (mixed-dementia support) ----
            # The cohort is NOT a monolith. Partition subjects so that AD-frame
            # subjects are staged even when recognized non-AD subjects (DLB/FTD/
            # VaD/PDD/NPH) are present in the same cohort. Only the biological
            # axis is exempt from differential partitioning (its tokens are
            # A/T(N) biomarker profiles, not clinical diagnoses), but the same
            # function is safe there because biomarker tokens are not in the
            # differential registry -> they all fall through as "AD states".
            part = _partition_cohort_by_frame(df)

            # Fail-closed: a subject carrying a token that is neither an AD
            # state nor a recognized non-AD/comorbidity token cannot be staged
            # OR honestly partitioned. Refuse the layer (never silently pass).
            if part["unrecognized"]:
                bad = "; ".join(
                    f"{sid}: {toks}" for sid, toks in
                    sorted(part["unrecognized"].items()))
                layers.append(LayerResult(
                    layer=layer, ran=False,
                    skipped_reason=(
                        "unrecognized_states: subject(s) carry tokens that are "
                        "neither AD-trajectory states nor recognized non-AD "
                        f"diagnoses [{bad}]. Add them to a rule pack or the "
                        "differential registry.")))
                continue

            ad_df = part["ad_df"]
            non_ad = part["non_ad"]
            comorbidity = part["comorbidity"]
            mixed_primary = part["mixed_primary"]

            # If NO subject is AD-frame (a pure non-AD cohort), do not refuse:
            # record the layer as ran-but-out-of-scope, reporting the recognized
            # non-AD partition honestly. (This is the "work always" contract:
            # the cohort is processed and reported, never hard-refused, while no
            # meaningless AD score is emitted.)
            if ad_df.empty:
                layers.append(LayerResult(
                    layer=layer, ran=True, audit_id=None,
                    summary={
                        "staged_ad_subjects": 0,
                        "out_of_ad_scope_subjects": len(non_ad),
                        "out_of_ad_scope": {k: non_ad[k] for k in sorted(non_ad)},
                        "note": ("no AD-spectrum subjects to stage; all "
                                 "recognized subjects are non-AD diagnoses "
                                 "(out of AD staging scope)")},
                    flags=[]))
                continue

            ad_states = ad_df["state"].tolist()
            try:
                pack_name, vm = select_rulepack_or_refuse(
                    ad_states, disease_domain=disease_domain)
            except VocabularyMismatchError as e:
                layers.append(LayerResult(layer=layer, ran=False,
                                          skipped_reason=f"vocabulary_mismatch: {e}"))
                continue
            lp = load_rulepack(pack_name)

            # NOTE on contamination vs. partitioning (deliberate design):
            # Tokens that are NOT recognized non-AD diagnoses (e.g. a biomarker
            # token like 'A+T+N+' wrongly placed in a clinical column, a token
            # from a different AD pack like 'Stage_3', or a typo) are NOT
            # isolated here. They remain in the AD partition so the auditor
            # FLAGS them as contamination / inadmissible -- that is a real data
            # error a sponsor must see, not an out-of-scope subject to hide.
            # Only registry-recognized non-AD primary subjects were partitioned
            # out above (into `non_ad`); only registry comorbidity tokens were
            # stripped (into `comorbidity`). vm.unmatched still reports any
            # contaminating tokens for transparency.
            isolated: dict[str, list[str]] = {}

            trajs = trajectories_from_dataframe(
                ad_df, patient_id_col="subject_id", visit_date_col="visit_date",
                state_col="state", skip_invalid=False)
            res = audit(trajs, lp, bootstrap_B=bootstrap_B, seed=seed,
                        return_per_transition=True)
            d = res.to_dict()
            packs_applied[f"{layer}:{pack_name}"] = d["rulepack"]["sha256"]
            sub_ids[layer] = d["audit_id"]
            fl = []
            pt = res.per_transition
            mixed_set = set(mixed_primary)
            for i in range(len(pt.flags)):
                if pt.flags[i]:
                    sid = pt.patient_ids[i]
                    # Q1 decision: for mixed-primary subjects, a non-AD component
                    # (e.g. DLB fluctuation) can legitimately explain a
                    # non-monotonic / reversion-type course, so such flags are
                    # surfaced at REVIEW tier (informational), NOT impossible.
                    # Genuine forward-impossible transitions are rare here and
                    # still reported -- but conservatively at review tier for a
                    # partial-frame subject, because AD rules only partly govern.
                    if str(sid) in mixed_set:
                        tier = TIER_INFORMATIONAL
                        fl.append({"subject_id": sid,
                                   "from": pt.from_states[i], "to": pt.to_states[i],
                                   "delta_days": float(pt.delta_days[i]),
                                   "tier": tier,
                                   "partial_frame": True,
                                   "non_ad_component": mixed_primary[str(sid)]})
                        severity[TIER_INFORMATIONAL] += 1
                    else:
                        fl.append({"subject_id": sid,
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
                         "contamination_tokens": list(vm.unmatched),
                         # mixed-dementia partition report (scope honesty):
                         "staged_ad_subjects": len(
                             [s for s in part["ad_subject_ids"]
                              if s not in isolated]),
                         "out_of_ad_scope_subjects": len(non_ad),
                         "out_of_ad_scope": {k: non_ad[k] for k in sorted(non_ad)},
                         "comorbidity_annotated": {k: comorbidity[k]
                                                   for k in sorted(comorbidity)},
                         "mixed_primary_partial_frame": {k: mixed_primary[k]
                                                         for k in sorted(mixed_primary)},
                         "unrecognized_isolated": isolated},
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
