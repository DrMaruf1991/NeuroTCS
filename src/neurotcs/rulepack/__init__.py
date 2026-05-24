"""
neurotcs.rulepack — Citation-locked clinical rule packs (Piece 3 of 7).

The 9 production rule packs span 6 disease domains and are anchored to
internationally endorsed published guidelines (NIA-AA 2018, AA 2024, AA 2024
TRAC, MDS-UPDRS / Hoehn-Yahr, McDonald 2024, RECIST 1.1, iRECIST, mRS,
Fleischner 2017). See docs/transcription_audit/ for per-pack YAML <-> source
verification.

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
