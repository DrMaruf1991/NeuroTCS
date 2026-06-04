"""neurotcs.orchestration.conversion_audit -- longitudinal conversion auditor.

USIL increment 3 (v1.61.0). Derives diagnostic conversion / reversion across the
canonical AD clinical-stage sequence (CN < SMC < EMCI < LMCI < MCI < AD) within
each subject's ordered visits, and classifies each between-visit transition into
a plausibility tier grounded in the published literature.

Why this is an honest auditor and not a guess:
* It reads ONLY the canonical clinical-stage labels NeuroTCS already audits; it
  derives no biomarker rule and invents no conversion window. (pMCI/sMCI labels
  are window-dependent operationalizations -- Moradi 2015 -- so we audit the
  OBSERVED transition direction, not a fixed window.)
* Forward progression (CN -> MCI -> AD) is the expected continuum (NIA-AA, Jack
  2018/2024).
* MCI -> CN reversion is a REAL, documented phenomenon (Canevelli 2016 pooled
  ~18%; Malek-Ahmadi 2016 ~24%), so it is flagged as PLAUSIBLE (informational),
  never as impossible and never rejected.
* Dementia(AD) -> CN is treated as implausible (a strong data-quality flag);
  AD -> a milder stage is implausible-for-review. No accepted clinical model has
  AD-dementia fully reverting to normal.
* Non-canonical labels or single-visit subjects produce NO transition flag
  (never guess).

Severity uses the EXISTING NeuroTCS tiers. This is an advisory overlay returned
for reporting; it does not mutate the deterministic flag pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Canonical clinical-stage ordering. SMC/EMCI/LMCI are ADNI sub-stages; the rank
# encodes the documented AD continuum DIRECTION (for detecting forward vs
# reversion) and is an ADNI-cohort ordering, not a universal clinical claim.
_STAGE_RANK: dict[str, int] = {
    "CN": 0,
    "SMC": 1,
    "EMCI": 2,
    "LMCI": 3,
    "MCI": 4,
    "AD": 5,
}

# tiers reuse the framework severity vocabulary
TIER_IMPOSSIBLE = "impossible"
TIER_IMPLAUSIBLE = "implausible"
TIER_INFORMATIONAL = "informational"

# Literature anchors recorded on emitted flags (verified DOIs/PMIDs).
_CITE_CONTINUUM = {"citation_pmid": "29653606",
                   "citation_doi": "10.1016/j.jalz.2018.02.018"}  # Jack 2018
_CITE_REVERSION = {"citation_pmid": "27502450",
                   "citation_doi": ""}  # Canevelli 2016 (MCI->CN reversion)


@dataclass(frozen=True)
class ConversionFlag:
    subject_id: str
    from_state: str
    to_state: str
    from_visit: object
    to_visit: object
    direction: str          # "forward" | "reversion" | "within_band"
    tier: str
    reason: str
    citation_pmid: str = ""
    citation_doi: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "subject_id": self.subject_id,
            "from": self.from_state,
            "to": self.to_state,
            "from_visit": self.from_visit,
            "to_visit": self.to_visit,
            "direction": self.direction,
            "tier": self.tier,
            "reason": self.reason,
            "citation_pmid": self.citation_pmid,
            "citation_doi": self.citation_doi,
        }


@dataclass(frozen=True)
class ConversionResult:
    flags: list[ConversionFlag] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)
    # subject_id -> derived label among {stable, converter, reverter, mixed}
    derived_labels: dict[str, str] = field(default_factory=dict)
    n_transitions: int = 0


def _classify(from_state: str, to_state: str) -> tuple[str, str, str, dict[str, str]] | None:
    """Return (direction, tier, reason, citation) for a transition, or None if
    either state is not canonical (never guess)."""
    rf = _STAGE_RANK.get(from_state)
    rt = _STAGE_RANK.get(to_state)
    if rf is None or rt is None:
        return None
    if rt > rf:
        return ("forward", TIER_INFORMATIONAL,
                "forward progression along the AD continuum (expected)",
                _CITE_CONTINUUM)
    if rt == rf:
        return None  # no change

    # rt < rf : a reversion. Severity depends on how far down and from where.
    from_is_dementia = from_state == "AD"
    to_is_normalish = to_state in ("CN", "SMC")
    # within the MCI band (EMCI/LMCI/MCI) reversion: plausible measurement noise
    mci_band = {"EMCI", "LMCI", "MCI"}
    if from_state in mci_band and to_state in mci_band:
        return ("within_band", TIER_INFORMATIONAL,
                "reversion within the MCI band (plausible; staging is graded)",
                _CITE_REVERSION)
    if from_is_dementia:
        # AD -> anything milder: no accepted model for AD-dementia reverting
        return ("reversion", TIER_IMPLAUSIBLE,
                "dementia(AD) reverting to a milder stage has no accepted "
                "clinical model; flag for data-quality review",
                _CITE_CONTINUUM)
    if to_is_normalish:
        # MCI/EMCI/LMCI/SMC -> CN/SMC : documented MCI->CN reversion
        return ("reversion", TIER_INFORMATIONAL,
                "reversion toward normal cognition is documented (plausible); "
                "flag for awareness, not rejection",
                _CITE_REVERSION)
    # any other downward step that is not dementia-origin and not to normal
    return ("reversion", TIER_INFORMATIONAL,
            "downward stage change (plausible); flag for awareness",
            _CITE_REVERSION)


def audit_conversions(
    rows: list[tuple[str, object, str]],
) -> ConversionResult:
    """Audit longitudinal stage conversions.

    rows: list of (subject_id, visit, state). Need not be pre-sorted; rows are
    grouped by subject and ordered by visit. Only canonical clinical-stage
    labels participate; subjects with <2 canonical-stage visits produce no
    transitions.
    """
    by_subject: dict[str, list[tuple[object, str]]] = {}
    for sid, visit, state in rows:
        by_subject.setdefault(str(sid), []).append((visit, str(state)))

    flags: list[ConversionFlag] = []
    severity = {TIER_IMPOSSIBLE: 0, TIER_IMPLAUSIBLE: 0, TIER_INFORMATIONAL: 0}
    derived: dict[str, str] = {}
    n_trans = 0

    for sid, visits in by_subject.items():
        # order by visit; visits may be ints or strings -> sort by (type-safe key)
        try:
            ordered = sorted(visits, key=lambda vs: (float(vs[0]),))
        except (TypeError, ValueError):
            ordered = sorted(visits, key=lambda vs: str(vs[0]))
        # keep only rows whose state is canonical for transition logic
        seq = [(v, s) for v, s in ordered if s in _STAGE_RANK]
        if len(seq) < 2:
            continue
        saw_forward = False
        saw_reversion = False
        for (v0, s0), (v1, s1) in zip(seq, seq[1:], strict=False):
            n_trans += 1
            res = _classify(s0, s1)
            if res is None:
                continue
            direction, tier, reason, cite = res
            if direction == "forward":
                saw_forward = True
            elif direction in ("reversion", "within_band"):
                saw_reversion = True
            severity[tier] += 1
            flags.append(ConversionFlag(
                subject_id=sid, from_state=s0, to_state=s1,
                from_visit=v0, to_visit=v1, direction=direction, tier=tier,
                reason=reason,
                citation_pmid=cite.get("citation_pmid", ""),
                citation_doi=cite.get("citation_doi", ""),
            ))
        # derived per-subject label (advisory)
        if saw_forward and saw_reversion:
            derived[sid] = "mixed"
        elif saw_forward:
            derived[sid] = "converter"
        elif saw_reversion:
            derived[sid] = "reverter"
        else:
            derived[sid] = "stable"

    return ConversionResult(
        flags=flags,
        severity_counts=severity,
        derived_labels=derived,
        n_transitions=n_trans,
    )
