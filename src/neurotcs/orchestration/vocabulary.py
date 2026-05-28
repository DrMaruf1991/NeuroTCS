"""neurotcs.orchestration.vocabulary -- vocabulary-match gating and
pack auto-selection (Invariant B: soundness).

Today's failure mode: feeding A/T tokens (A-T-, A+T-, A+T+) to a Stage_*
rule pack produced a cTCS of 0.8637 -- a number that looked like a coherence
score but was a vocabulary-mismatch artifact. This module makes that
impossible: before any staging audit runs, the data's state vocabulary must
match the selected pack's state_space above a threshold, or the framework
REFUSES (fail-closed) rather than emitting a meaningless score.
"""
from __future__ import annotations

from dataclasses import dataclass

from neurotcs.rulepack.loader import list_rulepacks, load_rulepack

# A staging audit is only sound if essentially all observed states are in the
# pack vocabulary. We require full coverage of the *changed* states; a single
# stray contaminating token (e.g. one A+T+ in a clinical column) is reported
# but does not by itself block -- it will surface as an inadmissible-transition
# flag. The gate blocks the systemic-mismatch case (the A/T-vs-Stage_* disaster).
DEFAULT_MATCH_THRESHOLD = 0.80


@dataclass(frozen=True)
class VocabularyMatch:
    """Result of comparing a data vocabulary against a pack's state_space.

    Two distinct quantities, because they answer different questions:

    - coverage_fraction = |distinct pack states seen in data| / |pack states|.
      "Does the data speak this pack's language?" Decides APPLICABILITY: a
      pack applies when its own vocabulary is substantially present in the
      data. The A/T-vs-Stage_* disaster had coverage 0.0.

    - contamination = distinct data states NOT in the pack vocabulary. NOT a
      reason to refuse the whole audit (they surface as inadmissible-transition
      flags); reported so the reader knows the data carried unrecognized tokens.
    """

    rulepack_id: str
    pack_states: tuple[str, ...]
    data_states: tuple[str, ...]
    matched: tuple[str, ...]            # data states that ARE in the pack
    unmatched: tuple[str, ...]          # contaminating data states NOT in pack
    pack_states_seen: tuple[str, ...]   # pack states actually present in data
    coverage_fraction: float            # |pack_states_seen| / |pack_states|
    contamination_fraction: float       # |unmatched| / |distinct data states|
    is_applicable: bool                 # coverage_fraction >= threshold


class VocabularyMismatchError(ValueError):
    """Raised when the data vocabulary does not match any/selected pack."""


def _pack_state_names(rulepack_name: str) -> tuple[str, ...]:
    lp = load_rulepack(rulepack_name)
    return tuple(s.name for s in lp.rulepack.state_space)


def assess_vocabulary(
    data_states: list[str],
    rulepack_name: str,
    *,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> VocabularyMatch:
    """Compare observed data states against a rule pack's state_space.

    coverage_fraction = |pack states present in data| / |pack states| ->
      decides applicability ("does the data speak this pack's language?").
    contamination_fraction = |data states not in pack| / |distinct data states|
      -> reported, not blocking.
    is_applicable = coverage_fraction >= threshold.
    """
    pack_states = _pack_state_names(rulepack_name)
    pack_set = set(pack_states)
    distinct = [s for s in dict.fromkeys(str(x) for x in data_states if x is not None)]
    data_set = set(distinct)
    matched = tuple(s for s in distinct if s in pack_set)
    unmatched = tuple(s for s in distinct if s not in pack_set)
    pack_seen = tuple(s for s in pack_states if s in data_set)
    coverage = (len(pack_seen) / len(pack_states)) if pack_states else 0.0
    contamination = (len(unmatched) / len(distinct)) if distinct else 0.0
    return VocabularyMatch(
        rulepack_id=load_rulepack(rulepack_name).rulepack.rulepack_id,
        pack_states=pack_states,
        data_states=tuple(distinct),
        matched=matched,
        unmatched=unmatched,
        pack_states_seen=pack_seen,
        coverage_fraction=coverage,
        contamination_fraction=contamination,
        is_applicable=coverage >= threshold,
    )


def select_rulepack_or_refuse(
    data_states: list[str],
    *,
    disease_domain: str | None = None,
    candidate_packs: list[str] | None = None,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> tuple[str, VocabularyMatch]:
    """Select the applicable rule pack (best vocabulary coverage), or refuse.

    Returns (rulepack_name, VocabularyMatch) for the best applicable pack.
    Raises VocabularyMismatchError if no production pack's vocabulary is
    substantially present in the data -- the fail-closed behavior that
    prevents a meaningless cTCS (the A/T-vs-Stage_* artifact).
    """
    if candidate_packs is None:
        packs = list_rulepacks()
        candidate_packs = [
            p["name"] for p in packs
            if p.get("status") == "production"
            and (disease_domain is None or p.get("disease_domain") == disease_domain)
        ]

    best_name: str | None = None
    best_match: VocabularyMatch | None = None
    for name in candidate_packs:
        vm = assess_vocabulary(data_states, name, threshold=threshold)
        if best_match is None or vm.coverage_fraction > best_match.coverage_fraction:
            best_name, best_match = name, vm

    if best_match is None or not best_match.is_applicable:
        distinct = sorted({str(x) for x in data_states if x is not None})
        tried = ", ".join(candidate_packs) if candidate_packs else "(none)"
        best_cov = f"{best_match.coverage_fraction:.2f}" if best_match else "n/a"
        raise VocabularyMismatchError(
            f"No production rule pack's vocabulary is present in the data "
            f"states {distinct} above coverage threshold {threshold:.2f} "
            f"(best coverage {best_cov}). Tried: {tried}. Refusing to emit a "
            f"staging score on mismatched vocabulary (fail-closed: a coherence "
            f"score on non-matching vocabulary is not a meaningful number)."
        )
    return best_name, best_match
