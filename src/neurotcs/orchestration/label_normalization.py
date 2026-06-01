"""neurotcs.orchestration.label_normalization -- subject-label synonym layer.

USIL increment 1 (v1.59.0). Normalizes the RAW clinical-stage labels different
AD studies use ("cognitively normal", "CU", "NC", "subjective memory complaint",
"early MCI", "Alzheimer's dementia", ...) into the canonical clinical-stage
vocabulary the staging rule packs already consume (CN / SMC / EMCI / LMCI / MCI
/ AD), from a citation-anchored YAML ontology.

Design guarantees (the NeuroTCS ethos -- never guess, fail honest):

* SYNONYMS ONLY. Maps different STRINGS for the SAME canonical label. It never
  collapses distinct clinical categories (no SMC->CN, no EMCI->MCI); those are
  diagnostic reinterpretations, out of scope.
* NEVER GUESS. Only exact (normalized) known synonyms are mapped. Anything
  unrecognized passes through UNCHANGED so it still surfaces as contamination in
  the vocabulary gate.
* AMBIGUITY-SAFE. The ontology is checked at load time for any synonym string
  that maps to >1 canonical (fail-closed if the data file is inconsistent). At
  normalize time a token that matches no group is left as-is; it is never
  coin-flipped.
* CITATION-ANCHORED + SHA-PINNED. Every group cites its source; the ontology
  file is hashed with the same cross-platform-stable hasher used for range packs.
* NON-DESTRUCTIVE + REPORTED. normalize_labels returns the exact mapping applied
  (raw -> canonical, with the matched synonym), so a bundle/stderr can record
  every substitution a regulator would want to see.
* OPT-IN. Nothing in this module runs unless a caller explicitly invokes it; the
  default audit path is unchanged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from neurotcs.clinical_ranges.yaml_hash import yaml_sha256_of_path

_ONTOLOGY_PATH = Path(__file__).resolve().parent / "label_ontology.yaml"

# Matching normalization: lowercase, strip, drop apostrophes, collapse any run of
# non-alphanumeric characters to a single space. Used ONLY to compare input
# tokens against synonyms; the OUTPUT is always the exact canonical string.
_PUNCT = re.compile(r"[^a-z0-9]+")


def _norm_token(s: str) -> str:
    s = str(s).strip().lower().replace("'", "")
    s = _PUNCT.sub(" ", s).strip()
    return s


@dataclass(frozen=True)
class LabelOntology:
    ontology_id: str
    domain: str
    status: str
    yaml_sha256: str
    # normalized synonym -> canonical label
    _index: dict[str, str]
    # canonical -> source citation key
    _source_by_canonical: dict[str, str]
    # citation key -> {pmid, doi, text}
    citations: dict[str, dict[str, str]]
    canonicals: tuple[str, ...]

    def canonical_for(self, raw: str) -> str | None:
        """Return the canonical label for a raw token, or None if unrecognized."""
        return self._index.get(_norm_token(raw))

    def citation_for(self, canonical: str) -> dict[str, str]:
        key = self._source_by_canonical.get(canonical, "")
        return self.citations.get(key, {})


class LabelOntologyError(ValueError):
    """Raised when the ontology data file is internally inconsistent."""


def load_label_ontology(path: Path | None = None) -> LabelOntology:
    p = path or _ONTOLOGY_PATH
    doc: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))

    citations: dict[str, dict[str, str]] = {}
    for c in doc.get("citations", []) or []:
        key = c.get("key")
        if not key:
            continue
        citations[key] = {
            "citation_pmid": str(c.get("citation_pmid", "") or ""),
            "citation_doi": str(c.get("citation_doi", "") or ""),
            "citation_text": " ".join(str(c.get("citation_text", "")).split()),
        }

    index: dict[str, str] = {}
    source_by_canonical: dict[str, str] = {}
    canonicals: list[str] = []
    # collision detection: a normalized synonym must map to exactly one canonical
    seen: dict[str, str] = {}

    for g in doc.get("groups", []) or []:
        canonical = g.get("canonical")
        if not canonical:
            raise LabelOntologyError("ontology group missing 'canonical'")
        canonicals.append(canonical)
        source_by_canonical[canonical] = g.get("source", "")
        # the canonical string is always a synonym of itself
        members = [canonical, *(g.get("synonyms") or [])]
        for syn in members:
            nt = _norm_token(syn)
            if not nt:
                continue
            if nt in seen and seen[nt] != canonical:
                raise LabelOntologyError(
                    f"synonym {syn!r} (normalized {nt!r}) maps to both "
                    f"{seen[nt]!r} and {canonical!r} -- ontology is ambiguous; "
                    f"fail-closed."
                )
            seen[nt] = canonical
            index[nt] = canonical

    return LabelOntology(
        ontology_id=doc.get("ontology_id", ""),
        domain=doc.get("domain", ""),
        status=doc.get("status", ""),
        yaml_sha256=yaml_sha256_of_path(p),
        _index=index,
        _source_by_canonical=source_by_canonical,
        citations=citations,
        canonicals=tuple(canonicals),
    )


@dataclass(frozen=True)
class NormalizationResult:
    """Outcome of normalizing a list of raw labels.

    normalized:   the labels after mapping (same length/order as input).
    mapping:      raw_token -> canonical, for tokens that WERE changed.
    unmatched:    distinct raw tokens that matched no synonym (left unchanged).
    applied:      list of {raw, canonical, matched_synonym, citation_*} records,
                  one per distinct mapped token, for provenance/reporting.
    ontology_id / ontology_sha256: identity of the ontology used.
    """
    normalized: list[str]
    mapping: dict[str, str]
    unmatched: list[str]
    applied: list[dict[str, str]] = field(default_factory=list)
    ontology_id: str = ""
    ontology_sha256: str = ""


def normalize_labels(
    raw_labels: list[str],
    ontology: LabelOntology | None = None,
) -> NormalizationResult:
    """Map raw clinical-stage labels onto the canonical vocabulary.

    A token is mapped only if it is an EXACT (normalized) synonym; otherwise it
    is passed through unchanged. Tokens already equal to a canonical label are
    left as-is (and not reported as 'changed'). Output preserves input order and
    length so it can replace a state column 1:1.
    """
    ont = ontology or load_label_ontology()
    normalized: list[str] = []
    mapping: dict[str, str] = {}
    unmatched_set: dict[str, None] = {}
    applied_by_raw: dict[str, dict[str, str]] = {}

    canonical_set = set(ont.canonicals)

    for raw in raw_labels:
        if raw is None:
            normalized.append(raw)  # preserve nulls untouched
            continue
        raw_s = str(raw)
        canon = ont.canonical_for(raw_s)
        if canon is None:
            normalized.append(raw_s)
            unmatched_set.setdefault(raw_s, None)
            continue
        normalized.append(canon)
        # only record as a real mapping if the string actually changed and the
        # raw token was not already a canonical label
        if raw_s != canon and raw_s not in canonical_set:
            mapping[raw_s] = canon
            if raw_s not in applied_by_raw:
                cit = ont.citation_for(canon)
                applied_by_raw[raw_s] = {
                    "raw": raw_s,
                    "canonical": canon,
                    "citation_pmid": cit.get("citation_pmid", ""),
                    "citation_doi": cit.get("citation_doi", ""),
                }

    return NormalizationResult(
        normalized=normalized,
        mapping=mapping,
        unmatched=list(unmatched_set.keys()),
        applied=list(applied_by_raw.values()),
        ontology_id=ont.ontology_id,
        ontology_sha256=ont.yaml_sha256,
    )
