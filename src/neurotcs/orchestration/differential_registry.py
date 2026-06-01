"""neurotcs.orchestration.differential_registry -- citation-locked recognition
of non-AD dementia diagnoses and AD comorbidity annotations.

WHY THIS EXISTS
---------------
Pure Alzheimer's disease is the MINORITY at autopsy in older cohorts. Real
research-hospital and trial cohorts routinely contain dementia with Lewy bodies
(DLB), frontotemporal dementia (FTD), vascular dementia (VaD), Parkinson's
disease dementia (PDD), and mixed presentations. Before this registry, any
cohort carrying such a token triggered a whole-cohort vocabulary-mismatch
refusal of the clinical staging layer -- so a single non-AD subject darkened
the audit for every stageable AD subject ("doesn't work always").

This registry lets the orchestrator PARTITION a cohort per-subject and route
each subject to the frame that legitimately governs it, instead of refusing the
whole cohort. It does NOT add staging rules for non-AD diseases (NeuroTCS stages
the AD trajectory; DLB/FTD/VaD have their own staging schemes out of scope). It
only RECOGNIZES these diagnoses by name so they can be reported as
out-of-AD-scope -- honest partitioning, not silent dropping.

THREE KINDS OF TOKEN
--------------------
1. NON_AD_PRIMARY -- a recognized non-AD dementia used as the subject's primary
   diagnosis/state (DLB, bvFTD, PPA, VaD, PDD, NPH). AD staging rules do NOT
   govern these (e.g. DLB's fluctuating cognition would false-flag as
   inadmissible reversion under AD rules). Subjects whose states are non-AD
   primary tokens are partitioned OUT and reported as out-of-AD-scope.

2. AD_COMORBIDITY -- a condition that co-occurs WITH AD as a stratifier but does
   not replace the AD clinical trajectory (cerebrovascular disease, white-matter
   hyperintensities, cerebral amyloid angiopathy, microbleeds). These ANNOTATE
   an AD subject (a safety stratifier, e.g. for ARIA risk); the AD axis is still
   staged normally.

3. (Everything else) -- a token that is neither an AD trajectory state nor a
   recognized non-AD/comorbidity token remains UNRECOGNIZED and continues to
   trigger fail-closed refusal-to-stage for that subject (never a silent pass).

All recognized tokens carry a verified primary-source citation (PMID/DOI). No
fabricated citations.
"""
from __future__ import annotations

from dataclasses import dataclass

# Token classes ------------------------------------------------------------
NON_AD_PRIMARY = "non_ad_primary"
AD_COMORBIDITY = "ad_comorbidity"


@dataclass(frozen=True)
class DifferentialEntry:
    """A recognized non-AD or comorbidity token with its consensus citation."""

    canonical: str          # canonical label (e.g. "DLB")
    kind: str               # NON_AD_PRIMARY | AD_COMORBIDITY
    full_name: str
    citation_pmid: str | None
    citation_doi: str | None
    citation_text: str
    aliases: tuple[str, ...]  # case-insensitive surface forms seen in data


# ---------------------------------------------------------------------------
# Citation-locked registry. Every PMID/DOI below was verified against the
# primary source (PubMed / publisher) on 2026-06-01. Do NOT edit a citation
# without re-verifying it.
# ---------------------------------------------------------------------------
_ENTRIES: tuple[DifferentialEntry, ...] = (
    DifferentialEntry(
        canonical="DLB",
        kind=NON_AD_PRIMARY,
        full_name="Dementia with Lewy bodies",
        citation_pmid="28592453",
        citation_doi="10.1212/WNL.0000000000004058",
        citation_text=(
            "McKeith IG, Boeve BF, Dickson DW, et al. Diagnosis and management "
            "of dementia with Lewy bodies: Fourth consensus report of the DLB "
            "Consortium. Neurology 2017;89(1):88-100. PMID 28592453, "
            "PMCID PMC5496518. DLB features fluctuating cognition, which under "
            "AD staging rules would false-flag as inadmissible reversion -- "
            "hence DLB is partitioned out of AD staging, not force-staged."
        ),
        aliases=("dlb", "lbd", "lewy body dementia", "lewy bodies",
                 "dementia with lewy bodies", "lewy body disease"),
    ),
    DifferentialEntry(
        canonical="bvFTD",
        kind=NON_AD_PRIMARY,
        full_name="Behavioural-variant frontotemporal dementia",
        citation_pmid="21810890",
        citation_doi="10.1093/brain/awr179",
        citation_text=(
            "Rascovsky K, Hodges JR, Knopman D, et al. Sensitivity of revised "
            "diagnostic criteria for the behavioural variant of frontotemporal "
            "dementia. Brain 2011;134(9):2456-2477. PMID 21810890. bvFTD "
            "presents with behavioural/executive change and relative sparing "
            "of episodic memory -- not an amnestic AD trajectory."
        ),
        aliases=("bvftd", "ftd", "ftld", "frontotemporal dementia",
                 "frontotemporal lobar degeneration", "behavioural variant ftd",
                 "behavioral variant ftd"),
    ),
    DifferentialEntry(
        canonical="PPA",
        kind=NON_AD_PRIMARY,
        full_name="Primary progressive aphasia",
        citation_pmid="21325651",
        citation_doi="10.1212/WNL.0b013e31821103e6",
        citation_text=(
            "Gorno-Tempini ML, Hillis AE, Weintraub S, et al. Classification of "
            "primary progressive aphasia and its variants. Neurology "
            "2011;76(11):1006-1014. PMID 21325651. PPA is a language-led "
            "syndrome (an FTLD-spectrum presentation), not amnestic AD staging."
        ),
        aliases=("ppa", "primary progressive aphasia", "svppa", "nfvppa",
                 "lvppa", "semantic dementia", "progressive nonfluent aphasia"),
    ),
    DifferentialEntry(
        canonical="VaD",
        kind=NON_AD_PRIMARY,
        full_name="Vascular dementia / vascular cognitive disorder (primary)",
        citation_pmid="24632990",
        citation_doi="10.1097/WAD.0000000000000034",
        citation_text=(
            "Sachdev P, Kalaria R, O'Brien J, et al. Diagnostic criteria for "
            "vascular cognitive disorders: a VASCOG statement. Alzheimer Dis "
            "Assoc Disord 2014;28(3):206-218. PMID 24632990. Used here for VaD "
            "as a PRIMARY diagnosis; vascular burden co-occurring WITH AD is "
            "handled separately as an AD_COMORBIDITY stratifier (see CVD)."
        ),
        aliases=("vad", "vascular dementia", "vascular cognitive impairment",
                 "vci", "vascular cognitive disorder", "multi-infarct dementia"),
    ),
    DifferentialEntry(
        canonical="PDD",
        kind=NON_AD_PRIMARY,
        full_name="Parkinson's disease dementia",
        citation_pmid="17542011",
        citation_doi="10.1002/mds.21507",
        citation_text=(
            "Emre M, Aarsland D, Brown R, et al. Clinical diagnostic criteria "
            "for dementia associated with Parkinson's disease. Mov Disord "
            "2007;22(12):1689-1707. PMID 17542011. PDD arises in established "
            "Parkinson's disease -- a Lewy-spectrum trajectory, not AD staging."
        ),
        aliases=("pdd", "parkinson disease dementia",
                 "parkinson's disease dementia", "pd dementia",
                 "parkinsons disease dementia"),
    ),
    DifferentialEntry(
        canonical="NPH",
        kind=NON_AD_PRIMARY,
        full_name="Normal pressure hydrocephalus",
        citation_pmid="16160425",
        citation_doi="10.1227/01.neu.0000168185.29659.c5",
        citation_text=(
            "Relkin N, Marmarou A, Klinge P, Bergsneider M, Black PM. "
            "Diagnosing idiopathic normal-pressure hydrocephalus. Neurosurgery "
            "2005;57(3 Suppl):S4-16. PMID 16160425. NPH is a potentially "
            "reversible non-degenerative dementia mimic -- not AD staging."
        ),
        aliases=("nph", "normal pressure hydrocephalus",
                 "idiopathic normal pressure hydrocephalus", "inph"),
    ),
    # ----- AD comorbidity stratifiers (annotate an AD subject; do NOT redirect) -----
    DifferentialEntry(
        canonical="CVD",
        kind=AD_COMORBIDITY,
        full_name="Cerebrovascular disease (comorbid with AD)",
        citation_pmid="21778438",
        citation_doi="10.1161/STR.0b013e3182299496",
        citation_text=(
            "Gorelick PB, Scuteri A, Black SE, et al. Vascular contributions to "
            "cognitive impairment and dementia: AHA/ASA statement. Stroke "
            "2011;42(9):2672-2713. PMID 21778438. Cerebrovascular disease "
            "co-occurring with AD is extremely common; it is a safety/severity "
            "stratifier and does NOT invalidate the AD clinical trajectory, so "
            "the AD axis is staged normally with this recorded as an annotation."
        ),
        aliases=("cvd", "cerebrovascular disease", "ad+cvd", "ad with cvd",
                 "ad+vascular", "mixed ad/vascular", "mixed ad-vascular",
                 "cerebrovascular"),
    ),
    DifferentialEntry(
        canonical="WMH",
        kind=AD_COMORBIDITY,
        full_name="White-matter hyperintensity burden (comorbid with AD)",
        citation_pmid="23867200",
        citation_doi="10.1016/S1474-4422(13)70124-8",
        citation_text=(
            "Wardlaw JM, Smith EE, Biessels GJ, et al. Neuroimaging standards "
            "for research into small vessel disease (STRIVE). Lancet Neurol "
            "2013;12(8):822-838. PMID 23867200. WMH burden is a small-vessel-"
            "disease stratifier annotating an AD subject; it does not replace "
            "the AD clinical trajectory."
        ),
        aliases=("wmh", "white matter hyperintensity",
                 "white matter hyperintensities", "leukoaraiosis",
                 "small vessel disease", "svd"),
    ),
    DifferentialEntry(
        canonical="CAA",
        kind=AD_COMORBIDITY,
        full_name="Cerebral amyloid angiopathy (comorbid with AD)",
        citation_pmid="35338085",
        citation_doi="10.1016/S1474-4422(21)00428-9",
        citation_text=(
            "Greenberg SM, Charidimou A. Diagnosis of cerebral amyloid "
            "angiopathy: the Boston criteria v2.0. Lancet Neurol "
            "2022;21(8):714-725. PMID 35338085. CAA / microbleeds are key "
            "anti-amyloid safety stratifiers (ARIA risk); recorded as an AD "
            "annotation, not a separate trajectory."
        ),
        aliases=("caa", "cerebral amyloid angiopathy", "microbleeds",
                 "cerebral microbleeds", "superficial siderosis"),
    ),
)

# Fast lookup: alias (lowercased) -> entry
_ALIAS_INDEX: dict[str, DifferentialEntry] = {}
for _e in _ENTRIES:
    _ALIAS_INDEX[_e.canonical.lower()] = _e
    for _a in _e.aliases:
        _ALIAS_INDEX[_a.lower()] = _e


def classify_token(token: str) -> DifferentialEntry | None:
    """Return the registry entry for a token, or None if unrecognized.

    Matching is case-insensitive and whitespace-trimmed. Unrecognized tokens
    return None (the caller must treat them fail-closed, never silently pass).
    """
    if token is None:
        return None
    key = str(token).strip().lower()
    return _ALIAS_INDEX.get(key)


def is_non_ad_primary(token: str) -> bool:
    e = classify_token(token)
    return e is not None and e.kind == NON_AD_PRIMARY


def is_ad_comorbidity(token: str) -> bool:
    e = classify_token(token)
    return e is not None and e.kind == AD_COMORBIDITY


def all_entries() -> tuple[DifferentialEntry, ...]:
    """All registry entries (stable order = definition order)."""
    return _ENTRIES
