"""
neurotcs.rulepack — Citation-locked clinical rule packs (Piece 3 of 7).

The 3 production rule packs cover Alzheimer's disease and are anchored to
internationally endorsed published guidelines (NIA-AA 2018 Framework,
AA 2024 Revised Criteria with Jack 2024 Table 7 integrated biological +
clinical staging, AA 2024 TRAC framework for anti-Aβ therapy trajectories).

**Scope (v1.9.0+):** NeuroTCS is an Alzheimer's-disease auditing tool. It
ships exactly the AD rule packs above; it does not contain, claim, or roadmap
any non-AD disease packs.

See docs/transcription_audit/ for per-pack YAML <-> source verification.

Public API:
    load_rulepack("ad/niaaa_2018")          -> LoadedRulePack
    list_rulepacks()                        -> list[dict] (summary)
    LoadedRulePack.assert_usable_for_audit()
"""

from neurotcs.rulepack.loader import (  # noqa: F401
    LoadedRulePack,
    RulePackLoadError,
    list_rulepacks,
    load_rulepack,
    load_rulepack_from_path,
)
from neurotcs.rulepack.schema import (  # noqa: F401
    SCHEMA_VERSION,
    Citation,
    DiseaseDomain,
    InadmissibleTransition,
    RulePack,
    RulePackStatus,
    State,
    Transition,
    TransitionPrior,
)

__all__ = [
    "SCHEMA_VERSION",
    "Citation",
    "DiseaseDomain",
    "InadmissibleTransition",
    "LoadedRulePack",
    "RulePack",
    "RulePackLoadError",
    "RulePackStatus",
    "State",
    "Transition",
    "TransitionPrior",
    "list_rulepacks",
    "load_rulepack",
    "load_rulepack_from_path",
]
