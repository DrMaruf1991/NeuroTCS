"""neurotcs.orchestration.atn_normalization -- biological A/T/N notation layer.

USIL increment 2 (v1.60.0). The biological mirror of the v1.59.0 clinical-stage
synonym layer. Normalizes the many ways studies write an NIA-AA AT(N) biomarker
profile -- "A+T-N+", "A+/T-/N+", "A pos T neg N pos", "amyloid positive, tau
negative, neurodegeneration positive" -- onto the EXACT canonical profile string
the biological staging packs consume (e.g. A+T-N+, or the 2-axis A+T-).

Why a SEPARATE module from label_normalization: that module's _norm_token strips
+/- (non-alphanumeric), which would collapse A+T+N+ and A-T-N- to the same key.
A biomarker normalizer MUST preserve sign semantics, so it parses axis+polarity
pairs and reassembles in canonical A,T,(N) order.

Safety guarantees (the NeuroTCS ethos -- never guess, fail honest):

* NOTATION ONLY. Re-expresses the SAME profile in canonical notation. It never
  changes polarity and never infers a missing axis.
* VERIFIED AGAINST THE PACK. A reassembled profile is emitted ONLY if it is an
  EXACT member of the target pack's state space. Reassembly can therefore never
  invent a profile the pack does not define; anything else passes through.
* NEVER GUESS. Unparseable tokens, conflicting duplicate axes, or an axis set
  whose arity matches no provided pack -> token passes through UNCHANGED.
* CITATION-ANCHORED. The AT(N) notation is anchored to Jack 2018 in the YAML.
* OPT-IN + REPORTED (wired via the shared --normalize-labels flag).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from neurotcs.clinical_ranges.yaml_hash import yaml_sha256_of_path

_ONTOLOGY_PATH = Path(__file__).resolve().parent / "atn_ontology.yaml"

# canonical axis order for reassembly
_AXIS_ORDER = ("A", "T", "N")


def _norm(s: str) -> str:
    """Lowercase + collapse whitespace; preserve +, -, and letters/digits."""
    return " ".join(str(s).strip().lower().split())


@dataclass(frozen=True)
class AtnOntology:
    ontology_id: str
    yaml_sha256: str
    # normalized axis word -> canonical axis letter (A/T/N)
    axis_index: dict[str, str]
    # normalized polarity word -> canonical sign (+/-)
    polarity_index: dict[str, str]
    citation: dict[str, str]


class AtnOntologyError(ValueError):
    """Raised when the ATN ontology data file is internally inconsistent."""


def load_atn_ontology(path: Path | None = None) -> AtnOntology:
    p = path or _ONTOLOGY_PATH
    doc: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))

    axis_index: dict[str, str] = {}
    for letter, words in (doc.get("axis_words") or {}).items():
        for w in words:
            key = _norm(w)
            if key in axis_index and axis_index[key] != letter:
                raise AtnOntologyError(
                    f"axis word {w!r} maps to both {axis_index[key]!r} and "
                    f"{letter!r} -- ambiguous; fail-closed.")
            axis_index[key] = letter

    polarity_index: dict[str, str] = {}
    for sign, words in (doc.get("polarity_words") or {}).items():
        for w in words:
            key = _norm(w)
            if key in polarity_index and polarity_index[key] != sign:
                raise AtnOntologyError(
                    f"polarity word {w!r} maps to both {polarity_index[key]!r} "
                    f"and {sign!r} -- ambiguous; fail-closed.")
            polarity_index[key] = sign

    cites = doc.get("citations") or []
    citation = {}
    if cites:
        c = cites[0]
        citation = {
            "citation_pmid": str(c.get("citation_pmid", "") or ""),
            "citation_doi": str(c.get("citation_doi", "") or ""),
        }

    return AtnOntology(
        ontology_id=doc.get("ontology_id", ""),
        yaml_sha256=yaml_sha256_of_path(p),
        axis_index=axis_index,
        polarity_index=polarity_index,
        citation=citation,
    )


# A profile token is a sequence of (axis-word, polarity) pairs. We tokenize on
# axis/polarity words and the compact "A+" punctuation form. The parser is
# deliberately strict: it recognizes axis letters A/T/N (compact) and the
# spelled-out axis/polarity words; anything it cannot fully resolve -> no map.
_COMPACT = re.compile(r"([atn])\s*([+\-])", re.IGNORECASE)
_WORD = re.compile(r"[a-z][a-z\-]*|[+\-]", re.IGNORECASE)


def _parse_profile(raw: str, ont: AtnOntology) -> dict[str, str] | None:
    """Parse a raw profile string into {axis: sign}, or None if not cleanly
    parseable. Tries the compact form (A+T-N+) first, then a word scan."""
    s = _norm(raw)

    # 1) compact form: runs of letter+sign, e.g. "a+t-n+" or "a+ t- n+"
    compact = _COMPACT.findall(s)
    # only accept compact if it consumes essentially the whole string (so we
    # do not silently ignore unexplained trailing content)
    if compact:
        consumed = "".join(f"{a}{p}" for a, p in compact)
        if len(consumed) == len(re.sub(r"[\s/|,]", "", s)):
            axes: dict[str, str] = {}
            for a, p in compact:
                letter = a.upper()
                if letter in axes and axes[letter] != p:
                    return None  # conflicting duplicate axis
                axes[letter] = p
            return axes or None

    # 2) word scan: alternating axis-word and polarity-word tokens.
    tokens = _WORD.findall(s)
    axes = {}
    i = 0
    pending_axis: str | None = None
    saw_any = False
    while i < len(tokens):
        tok = tokens[i]
        axis = ont.axis_index.get(tok)
        pol = ont.polarity_index.get(tok)
        if axis is not None:
            if pending_axis is not None:
                return None  # two axes in a row without a polarity -> ambiguous
            pending_axis = axis
        elif pol is not None:
            if pending_axis is None:
                return None  # polarity without a preceding axis -> ambiguous
            if pending_axis in axes and axes[pending_axis] != pol:
                return None  # conflicting duplicate axis
            axes[pending_axis] = pol
            pending_axis = None
            saw_any = True
        else:
            # an unrecognized word -> we cannot cleanly parse this token
            return None
        i += 1
    if pending_axis is not None or not saw_any:
        return None
    return axes or None


@dataclass(frozen=True)
class AtnNormalizationResult:
    normalized: list[str]
    mapping: dict[str, str]
    unmatched: list[str]
    applied: list[dict[str, str]] = field(default_factory=list)
    ontology_id: str = ""
    ontology_sha256: str = ""


def normalize_atn_labels(
    raw_labels: list[str],
    valid_states: set[str],
    ontology: AtnOntology | None = None,
) -> AtnNormalizationResult:
    """Normalize raw A/T/N profile labels to canonical profile strings.

    valid_states: the target pack's state_space (e.g. ad/atn_2018's 8 profiles
    or ad/at_biological's 3). A reassembled profile is emitted ONLY if it is an
    exact member of this set. The reassembly arity is taken from the parsed axes
    (A,T or A,T,N) and the canonical string is built in A,T,(N) order, so it can
    match either a 2-axis or 3-axis pack as appropriate.
    """
    ont = ontology or load_atn_ontology()
    normalized: list[str] = []
    mapping: dict[str, str] = {}
    unmatched: dict[str, None] = {}
    applied_by_raw: dict[str, dict[str, str]] = {}

    for raw in raw_labels:
        if raw is None:
            normalized.append(raw)
            continue
        raw_s = str(raw)
        # already canonical? leave as-is (idempotent), not reported as changed
        if raw_s in valid_states:
            normalized.append(raw_s)
            continue
        axes = _parse_profile(raw_s, ont)
        if not axes:
            normalized.append(raw_s)
            unmatched.setdefault(raw_s, None)
            continue
        # reassemble in canonical order using exactly the axes present
        present = [ax for ax in _AXIS_ORDER if ax in axes]
        # require a contiguous prefix of the axis order (A; A,T; or A,T,N) so a
        # stray {A,N} without T cannot form a bogus profile
        if present != list(_AXIS_ORDER[:len(present)]):
            normalized.append(raw_s)
            unmatched.setdefault(raw_s, None)
            continue
        candidate = "".join(f"{ax}{axes[ax]}" for ax in present)
        if candidate in valid_states:
            normalized.append(candidate)
            if candidate != raw_s:
                mapping[raw_s] = candidate
                if raw_s not in applied_by_raw:
                    applied_by_raw[raw_s] = {
                        "raw": raw_s,
                        "canonical": candidate,
                        "citation_pmid": ont.citation.get("citation_pmid", ""),
                        "citation_doi": ont.citation.get("citation_doi", ""),
                    }
        else:
            # parsed cleanly but the profile is not a state this pack defines
            # -> do NOT emit (never invent a profile); pass through.
            normalized.append(raw_s)
            unmatched.setdefault(raw_s, None)

    return AtnNormalizationResult(
        normalized=normalized,
        mapping=mapping,
        unmatched=list(unmatched.keys()),
        applied=list(applied_by_raw.values()),
        ontology_id=ont.ontology_id,
        ontology_sha256=ont.yaml_sha256,
    )
