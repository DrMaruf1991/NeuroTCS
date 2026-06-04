"""neurotcs.orchestration.disease_control -- non-AD differential-diagnosis layer.

USIL increment 3 (v1.61.0). Recognizes which subjects carry a NON-Alzheimer's
dementia / dementia-mimic label (vascular dementia, DLB, PDD, bvFTD, PPA, iNPH,
TES, autoimmune encephalitis, mixed dementia, CBD, PSP, depression-related
cognitive impairment), each anchored to its primary consensus diagnostic-criteria
citation, so AD-staging coverage stays scope-honest: a non-AD subject is recorded
as out-of-AD-scope rather than silently forced through the AD clinical-stage
vocabulary.

This is RECOGNITION, not diagnosis and not normalization:
* it never relabels a subject to an AD stage,
* it never asserts the subject truly has the condition -- it recognizes which
  published category the dataset's label refers to,
* unrecognized labels pass through (never guess),
* an ambiguous ontology (a synonym mapping to two categories) fails closed.

The string-normalization primitive (_norm_token) is reused from
label_normalization to avoid duplicating matching logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from neurotcs.clinical_ranges.yaml_hash import yaml_sha256_of_path
from neurotcs.orchestration.label_normalization import _norm_token

_ONTOLOGY_PATH = Path(__file__).resolve().parent / "disease_control_ontology.yaml"


class DiseaseControlOntologyError(ValueError):
    """Raised when the disease-control ontology data file is inconsistent."""


@dataclass(frozen=True)
class DiseaseControlOntology:
    ontology_id: str
    yaml_sha256: str
    # normalized synonym -> canonical category
    _index: dict[str, str]
    # canonical -> citation key
    _source_by_canonical: dict[str, str]
    # citation key -> {pmid, doi, text}
    citations: dict[str, dict[str, str]]
    canonicals: tuple[str, ...]
    abbrev_by_canonical: dict[str, str]

    def category_for(self, raw: str) -> str | None:
        return self._index.get(_norm_token(raw))

    def citation_for(self, canonical: str) -> dict[str, str]:
        return self.citations.get(self._source_by_canonical.get(canonical, ""), {})


def load_disease_control_ontology(path: Path | None = None) -> DiseaseControlOntology:
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
    abbrev_by_canonical: dict[str, str] = {}
    canonicals: list[str] = []
    seen: dict[str, str] = {}

    for g in doc.get("groups", []) or []:
        canonical = g.get("canonical")
        if not canonical:
            raise DiseaseControlOntologyError("group missing 'canonical'")
        canonicals.append(canonical)
        source_by_canonical[canonical] = g.get("source", "")
        abbrev_by_canonical[canonical] = g.get("abbrev", canonical)
        members = [canonical, g.get("abbrev", ""), *(g.get("synonyms") or [])]
        for syn in members:
            if not syn:
                continue
            nt = _norm_token(syn)
            if not nt:
                continue
            if nt in seen and seen[nt] != canonical:
                raise DiseaseControlOntologyError(
                    f"synonym {syn!r} (normalized {nt!r}) maps to both "
                    f"{seen[nt]!r} and {canonical!r} -- ambiguous; fail-closed.")
            seen[nt] = canonical
            index[nt] = canonical

    return DiseaseControlOntology(
        ontology_id=doc.get("ontology_id", ""),
        yaml_sha256=yaml_sha256_of_path(p),
        _index=index,
        _source_by_canonical=source_by_canonical,
        citations=citations,
        canonicals=tuple(canonicals),
        abbrev_by_canonical=abbrev_by_canonical,
    )


@dataclass(frozen=True)
class DiseaseControlResult:
    """Which (subject -> canonical non-AD category) pairs were recognized.

    recognized: subject_id -> {category, citation_pmid, citation_doi} for every
                subject whose label matched a disease-control category.
    by_category: canonical -> sorted list of subject_ids (for cohort summary).
    ontology_id / ontology_sha256: identity of the ontology used.
    """
    recognized: dict[str, dict[str, str]] = field(default_factory=dict)
    by_category: dict[str, list[str]] = field(default_factory=dict)
    ontology_id: str = ""
    ontology_sha256: str = ""


def recognize_disease_controls(
    subject_labels: list[tuple[str, str]],
    ontology: DiseaseControlOntology | None = None,
) -> DiseaseControlResult:
    """Recognize non-AD disease-control subjects.

    subject_labels: list of (subject_id, raw_label). A subject is recognized if
    ANY of its labels matches a disease-control category. (Datasets often repeat
    the cohort label per visit; we collapse to one decision per subject. If a
    subject shows two DIFFERENT recognized categories across rows, the first
    encountered is kept and the conflict is left to higher-level review -- we do
    not guess which is correct.)
    """
    ont = ontology or load_disease_control_ontology()
    recognized: dict[str, dict[str, str]] = {}
    by_category: dict[str, set[str]] = {}

    for subject_id, raw in subject_labels:
        if raw is None:
            continue
        sid = str(subject_id)
        if sid in recognized:
            continue  # already classified this subject
        cat = ont.category_for(str(raw))
        if cat is None:
            continue
        cit = ont.citation_for(cat)
        recognized[sid] = {
            "category": cat,
            "citation_pmid": cit.get("citation_pmid", ""),
            "citation_doi": cit.get("citation_doi", ""),
        }
        by_category.setdefault(cat, set()).add(sid)

    return DiseaseControlResult(
        recognized=recognized,
        by_category={k: sorted(v) for k, v in sorted(by_category.items())},
        ontology_id=ont.ontology_id,
        ontology_sha256=ont.yaml_sha256,
    )
