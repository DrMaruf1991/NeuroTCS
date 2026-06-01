"""
neurotcs.provenance -- Primary-source citation & verbatim-quote registry
=======================================================================

A single, regression-locked record of every external citation NeuroTCS relies
on, with its identifiers (DOI/PMID) and the date each was verified against the
PRIMARY source (publisher / PubMed / PMC), plus the verbatim quote blocks that
were checked word-for-word.

Why this module exists
----------------------
For a regulatory (21 CFR Part 11 / GxP) conversation, "the citations look
right" is not enough -- the verification must itself be reproducible and
tamper-evident. This registry is the auditable artifact: it states exactly
which identifiers were confirmed, against which source, on which date, and the
test suite (tests/provenance/) asserts that the constants scattered across the
codebase match this registry. If anyone edits a DOI/PMID or a verbatim quote in
a rule pack or module without updating the verified registry, the provenance
test fails -- the drift cannot pass silently.

Verification method (each entry, VERIFICATION_DATE)
---------------------------------------------------
Identifiers were checked against the publisher page AND PubMed/PMC. Verbatim
quotes were compared word-for-word against the publisher full text. Entries
whose quote text is reproduced below were confirmed EXACT; entries marked
``quote_verified=False`` carry only identifier verification (the module
paraphrases rather than quoting, so no verbatim check applies).

This module records facts; it imports nothing from the rest of NeuroTCS so it
can be read in isolation by an auditor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "VERIFICATION_DATE",
    "VerifiedCitation",
    "REGISTRY",
    "citation",
]

# ISO date on which the identifiers/quotes below were last verified against
# primary sources. Bump this only when re-verification is performed.
VERIFICATION_DATE = "2026-06-01"


@dataclass(frozen=True)
class VerifiedCitation:
    """One primary-source citation, verified against the publisher + PubMed/PMC."""

    key: str
    short: str
    doi: str
    pmid: str
    source: str  # where it was verified (publisher / PMC / PubMed)
    quote_verified: bool = False
    # verbatim quote blocks confirmed word-for-word against the primary source.
    verified_quotes: tuple[str, ...] = field(default_factory=tuple)


REGISTRY: dict[str, VerifiedCitation] = {
    "jack_2024": VerifiedCitation(
        key="jack_2024",
        short=(
            "Jack CR Jr, et al. Revised criteria for diagnosis and staging of "
            "Alzheimer's disease: Alzheimer's Association Workgroup. "
            "Alzheimers Dement 2024;20(8):5143-5169."
        ),
        doi="10.1002/alz.13859",
        pmid="38934362",
        source="Wiley Online Library (alz-journals) + PubMed",
        quote_verified=True,
        verified_quotes=(
            # Sec 3 inadmissibility keystone (ASCII hyphen per strict-ASCII codebase;
            # primary source renders it with a Unicode minus -- same words)
            "The A-T2+ biomarker profile is not consistent with a "
            "diagnosis of AD.",
            # Sec 4.3 stereotypical sequence
            "abnormal amyloid PET (A) precedes tau PET (T2), which, in turn, "
            "leads to neurodegeneration (N) and clinical symptoms (C), A to "
            "T2 to N to C.",
            # Sec 5.2 Stage 0
            "Stage 0 represents part of the AD continuum and is defined as "
            "genetically determined AD (which includes ADAD or DSAD)",
            # Sec 4.6 moderate(C)/high(D) cutpoint (verified verbatim 2026-06-01)
            "the distinction between moderate (stage C) and high (stage D) "
            "neocortical tau uptake could be operationalized in different ways.",
        ),
    ),
    "kwong_2022": VerifiedCitation(
        key="kwong_2022",
        short=(
            "Kwong JCC, et al. The silent trial - the bridge between "
            "bench-to-bedside clinical AI applications. "
            "Front Digit Health 2022;4:929508."
        ),
        doi="10.3389/fdgth.2022.929508",
        pmid="36052317",
        source="Frontiers + PMC (PMC9424628) + PubMed",
        quote_verified=True,
        verified_quotes=(
            "(1) exploratory model development, (2) a silent trial, and "
            "(3) prospective clinical evaluation.",
        ),
    ),
    "decide_ai_2022": VerifiedCitation(
        key="decide_ai_2022",
        short=(
            "Vasey B, et al; DECIDE-AI expert group. Reporting guideline for "
            "the early-stage clinical evaluation of decision support systems "
            "driven by artificial intelligence: DECIDE-AI. "
            "Nat Med 2022;28(5):924-933."
        ),
        doi="10.1038/s41591-022-01772-9",
        pmid="35585196",
        source="Nature Medicine + institutional repositories + PubMed",
        quote_verified=False,
    ),
    "larson_2025": VerifiedCitation(
        key="larson_2025",
        short=(
            "Larson DB, Bhargavan-Chatfield M, Tilkin M, Coombs L, Wald C. "
            "The Road Map for ACR Practice Accreditation for Radiology "
            "Artificial Intelligence. J Am Coll Radiol 2025;22(5):586-592."
        ),
        doi="10.1016/j.jacr.2025.02.008",
        pmid="40057886",
        source="JACR (ScienceDirect) + PubMed",
        quote_verified=True,
        verified_quotes=(
            "real-world performance often differs from that demonstrated in "
            "premarket testing",
        ),
    ),
    "future_ai_2024": VerifiedCitation(
        key="future_ai_2024",
        short=(
            "Lekadir K, et al. FUTURE-AI: international consensus guideline for "
            "trustworthy and deployable artificial intelligence in healthcare. "
            "BMJ 2025."
        ),
        doi="10.1136/bmj-2024-081554",
        pmid="39909534",
        source="BMJ + PubMed",
        quote_verified=False,
    ),
    "riley_2024": VerifiedCitation(
        key="riley_2024",
        short=(
            "Riley RD, et al. Minimum sample size for external validation of a "
            "clinical prediction model. BMJ (sample-size guidance)."
        ),
        doi="10.1136/bmj-2023-074821",
        pmid="38253388",
        source="BMJ + PubMed",
        quote_verified=False,
    ),
}


def citation(key: str) -> VerifiedCitation:
    """Return the verified citation record for ``key`` (KeyError if unknown)."""
    return REGISTRY[key]
