"""neurotcs.orchestration.aria_grade -- ARIA severity recognition (vocabulary) layer.

Recognizes free-text Amyloid-Related Imaging Abnormalities (ARIA) severity
labels and resolves them to a canonical (type, grade) pair on the four-level
scheme {none, mild, moderate, severe} for three finding types -- ARIA-E,
ARIA-H microhemorrhage, ARIA-H superficial siderosis -- plus macrohemorrhage
recognized as a SEPARATE finding (not a graded tier).

This is the companion of the numeric range pack ad/aria_safety: this layer maps
a label to a canonical (type, grade); the range pack validates a measured value
(FLAIR cm, microhemorrhage count, siderosis focal-area count) against the
verbatim FDA-label / ASNR grade boundaries. This layer encodes NO numeric
cutoff and makes NO diagnosis -- it only normalizes how a grade is written.

Safety: recognition only; unrecognized labels pass through (never guess);
ambiguous ontology fails closed at load; macrohemorrhage is never folded into a
mild/moderate/severe ARIA-H tier. The string-normalization primitive
(_norm_token) is reused from label_normalization to avoid duplicating matching
logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from neurotcs.clinical_ranges.yaml_hash import yaml_sha256_of_path
from neurotcs.orchestration.label_normalization import _norm_token

_ONTOLOGY_PATH = Path(__file__).resolve().parent / "aria_grade_ontology.yaml"

_GRADES = ("none", "mild", "moderate", "severe")
_TYPES = ("aria_e", "aria_h_microhemorrhage", "aria_h_siderosis", "macrohemorrhage", "none")


class AriaGradeOntologyError(ValueError):
    """Raised when the ARIA grade ontology data file is inconsistent."""


@dataclass(frozen=True)
class AriaGradeOntology:
    ontology_id: str
    yaml_sha256: str
    # normalized exact canonical label -> (type, grade)
    _label_index: dict[str, tuple[str, str]]
    # normalized grade word -> canonical grade
    _grade_index: dict[str, str]
    # normalized type word -> canonical type
    _type_index: dict[str, str]
    citations: dict[str, dict[str, str]]

    def resolve(self, raw: str) -> tuple[str, str] | None:
        """Resolve a raw ARIA label to a canonical (type, grade), or None.

        Resolution order:
          1. exact canonical label match (e.g. "ARIA-E moderate");
          2. token-based: find a recognized TYPE token and a recognized GRADE
             token within the normalized string. Macrohemorrhage resolves to
             (macrohemorrhage, "") with no grade (separate finding). A bare
             "no aria"/"none" resolves to (none, none).
        Ambiguity (two different recognized types in one string) -> None
        (fail-closed: never guess which finding the label means).
        """
        nt = _norm_token(raw)
        if not nt:
            return None
        if nt in self._label_index:
            return self._label_index[nt]

        tokens = nt.split()
        token_set = set(tokens)

        # detect "none"/"no aria" -> (none, none)
        if nt in ("no aria", "none", "no", "negative", "absent"):
            return ("none", "none")

        # find recognized type word(s) -- check multiword type synonyms too
        found_types: set[str] = set()
        for type_phrase, canonical in self._type_index.items():
            if type_phrase in nt:
                found_types.add(canonical)

        # Detect a bare ARIA-H family signal (e.g. "aria h" without the
        # microhemorrhage/siderosis subtype word). If present ALONGSIDE an
        # ARIA-E signal, the string names two findings -> ambiguous, fail
        # closed. A bare ARIA-H with no subtype and no ARIA-E is also
        # unresolvable (we never guess micro vs siderosis).
        bare_h = ("aria h" in nt) and not (
            found_types & {"aria_h_microhemorrhage", "aria_h_siderosis"})
        if bare_h and "aria_e" in found_types:
            return None  # names both ARIA-E and ARIA-H -> ambiguous
        if bare_h and not found_types:
            return None  # bare ARIA-H, no subtype -> never guess

        if len(found_types) > 1:
            return None  # ambiguous: more than one finding type named
        if not found_types:
            return None
        ctype = next(iter(found_types))

        if ctype == "macrohemorrhage":
            return ("macrohemorrhage", "")  # separate finding, no graded tier

        # find a grade token
        found_grades: set[str] = set()
        for gtoken in token_set:
            if gtoken in self._grade_index:
                found_grades.add(self._grade_index[gtoken])
        # also check multiword grade phrases (e.g. "grade 2")
        for gphrase, canonical in self._grade_index.items():
            if " " in gphrase and gphrase in nt:
                found_grades.add(canonical)
        if len(found_grades) != 1:
            return None  # no grade, or conflicting grades -> never guess
        return (ctype, next(iter(found_grades)))

    def citation_for(self, key: str) -> dict[str, str]:
        return self.citations.get(key, {})


def load_aria_grade_ontology(path: Path | None = None) -> AriaGradeOntology:
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

    # grade synonyms
    grade_index: dict[str, str] = {}
    seen_grade: dict[str, str] = {}
    for grade, syns in (doc.get("grade_synonyms") or {}).items():
        if grade not in _GRADES:
            raise AriaGradeOntologyError(f"unknown grade {grade!r}")
        for syn in syns or []:
            nt = _norm_token(syn)
            if not nt:
                continue
            if nt in seen_grade and seen_grade[nt] != grade:
                raise AriaGradeOntologyError(
                    f"grade synonym {syn!r} maps to both {seen_grade[nt]!r} "
                    f"and {grade!r} -- ambiguous; fail-closed.")
            seen_grade[nt] = grade
            grade_index[nt] = grade

    # type synonyms
    type_index: dict[str, str] = {}
    seen_type: dict[str, str] = {}
    for ctype, syns in (doc.get("type_synonyms") or {}).items():
        if ctype not in _TYPES:
            raise AriaGradeOntologyError(f"unknown type {ctype!r}")
        for syn in syns or []:
            nt = _norm_token(syn)
            if not nt:
                continue
            if nt in seen_type and seen_type[nt] != ctype:
                raise AriaGradeOntologyError(
                    f"type synonym {syn!r} maps to both {seen_type[nt]!r} "
                    f"and {ctype!r} -- ambiguous; fail-closed.")
            seen_type[nt] = ctype
            type_index[nt] = ctype

    # exact canonical labels
    label_index: dict[str, tuple[str, str]] = {}
    for entry in doc.get("canonical_labels", []) or []:
        label = entry.get("label")
        ctype = entry.get("type")
        grade = entry.get("grade")
        if ctype not in _TYPES:
            raise AriaGradeOntologyError(f"canonical label bad type {ctype!r}")
        if grade not in (*_GRADES, ""):
            raise AriaGradeOntologyError(f"canonical label bad grade {grade!r}")
        nt = _norm_token(label)
        if nt in label_index and label_index[nt] != (ctype, grade):
            raise AriaGradeOntologyError(
                f"canonical label {label!r} maps to two (type,grade) pairs -- "
                f"ambiguous; fail-closed.")
        label_index[nt] = (ctype, grade)

    return AriaGradeOntology(
        ontology_id=doc.get("ontology_id", ""),
        yaml_sha256=yaml_sha256_of_path(p),
        _label_index=label_index,
        _grade_index=grade_index,
        _type_index=type_index,
        citations=citations,
    )


@dataclass(frozen=True)
class AriaRecognitionResult:
    """Which (subject -> canonical ARIA (type, grade)) pairs were recognized.

    recognized: subject_id -> {type, grade, citation_pmid, citation_doi}.
    by_type: canonical type -> sorted list of subject_ids.
    ontology_id / ontology_sha256: identity of the ontology used.
    """
    recognized: dict[str, dict[str, str]] = field(default_factory=dict)
    by_type: dict[str, list[str]] = field(default_factory=dict)
    ontology_id: str = ""
    ontology_sha256: str = ""


def recognize_aria_grades(
    subject_labels: list[tuple[str, str]],
    ontology: AriaGradeOntology | None = None,
) -> AriaRecognitionResult:
    """Recognize ARIA severity labels for subjects.

    subject_labels: list of (subject_id, raw_label). A subject is recognized if
    its label resolves to a canonical (type, grade). The newest consensus
    citation (van Etten 2026) is attached to each recognition. Unrecognized
    labels are skipped (never guessed).
    """
    ont = ontology or load_aria_grade_ontology()
    cit = ont.citation_for("van_etten_2026")
    recognized: dict[str, dict[str, str]] = {}
    by_type: dict[str, set[str]] = {}

    for subject_id, raw in subject_labels:
        if raw is None:
            continue
        sid = str(subject_id)
        if sid in recognized:
            continue
        res = ont.resolve(str(raw))
        if res is None:
            continue
        ctype, grade = res
        recognized[sid] = {
            "type": ctype,
            "grade": grade,
            "citation_pmid": cit.get("citation_pmid", ""),
            "citation_doi": cit.get("citation_doi", ""),
        }
        by_type.setdefault(ctype, set()).add(sid)

    return AriaRecognitionResult(
        recognized=recognized,
        by_type={k: sorted(v) for k, v in sorted(by_type.items())},
        ontology_id=ont.ontology_id,
        ontology_sha256=ont.yaml_sha256,
    )
