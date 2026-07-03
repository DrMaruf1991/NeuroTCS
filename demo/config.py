"""Cohort registry + locked invariants for the NeuroTCS live web demo.

Single source of truth for:
  * which 5 cohorts the demo exposes,
  * where each cohort's DUA data lives (ENV-driven, never a hardcoded path),
  * the LOCKED cTCS / transition / flagged invariants the web MUST reproduce.

Data paths come exclusively from environment variables (the same ones the
shipped ``tests/audit_core/test_real_*_audit.py`` invariants read), so the DUA
files stay on the private server and never enter the repo. Nothing here embeds
a secret or a raw record.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CohortSpec:
    """Static description of one auditable cohort.

    Attributes:
        cohort_id: stable id, the ``--cohort`` value and URL segment.
        display_name: human label for the UI.
        env_vars: ordered env var names holding the data path; first one set
            wins (mirrors the shipped tests, incl. legacy aliases).
        input_hint: human description of the expected input (shown in /api/cohorts).
        is_directory: True for MIRIAD (a folder of 3 XNAT CSVs); False otherwise.
        locked_ctcs / locked_n_transitions / locked_n_flagged: the invariants the
            web result is checked against (see demo/CLAUDE.md and the real_* tests).
        note: one-line explanation of the cohort's cTCS position (for the UI).
    """

    cohort_id: str
    display_name: str
    env_vars: tuple[str, ...]
    input_hint: str
    is_directory: bool
    locked_ctcs: float
    locked_n_transitions: int
    locked_n_flagged: int
    note: str


# cTCS parity tolerance (framework standard) and EXACT count matching.
CTCS_ABS_TOL = 0.0005

# The five cohorts, in the order the CLAUDE.md invariant table lists them.
COHORTS: tuple[CohortSpec, ...] = (
    CohortSpec(
        cohort_id="a4",
        display_name="A4/LEARN",
        env_vars=("NEUROTCS_A4_CDR",),
        input_hint="A4Learn/Raw Data/cdr.csv",
        is_directory=False,
        locked_ctcs=0.996374,
        locked_n_transitions=8892,
        locked_n_flagged=34,
        note="Preclinical (amyloid-positive cognitively-unimpaired): most "
        "subjects CN, few admissible transitions -> highest cTCS.",
    ),
    CohortSpec(
        cohort_id="nacc",
        display_name="NACC",
        env_vars=("NEUROTCS_NACC_CSV",),
        input_hint="investigator_nacc73.csv",
        is_directory=False,
        locked_ctcs=0.991502,
        locked_n_transitions=158423,
        locked_n_flagged=1217,
        note="Large multi-center clinical cohort; broadest trajectory base.",
    ),
    CohortSpec(
        cohort_id="oasis3",
        display_name="OASIS-3",
        env_vars=("NEUROTCS_OASIS3_CDR", "NEUROTCS_OASIS3_UDSB4"),
        input_hint="OASIS3_UDSb4_cdr.csv",
        is_directory=False,
        locked_ctcs=0.9942,
        locked_n_transitions=7248,
        locked_n_flagged=30,
        note="Longitudinal CDR-staged research cohort.",
    ),
    CohortSpec(
        cohort_id="adni",
        display_name="ADNI",
        env_vars=("NEUROTCS_ADNI_DXSUM_RDA",),
        input_hint="ADNIMERGE2/data/DXSUM.rda",
        is_directory=False,
        locked_ctcs=0.994575,
        locked_n_transitions=12006,
        locked_n_flagged=65,
        note="DXSUM diagnostic-summary staging from the ADNIMERGE2 R package.",
    ),
    CohortSpec(
        cohort_id="miriad",
        display_name="MIRIAD",
        env_vars=("NEUROTCS_MIRIAD_DIR",),
        input_hint="MIRIAD directory (3 XNAT CSVs: clinical + sessions + subjects)",
        is_directory=True,
        locked_ctcs=0.985369,
        locked_n_transitions=454,
        locked_n_flagged=7,
        note="MMSE-staged (not CDR): coarser staging on a small cohort -> "
        "lowest cTCS. A real, explainable pattern, not an error.",
    ),
)

COHORTS_BY_ID: dict[str, CohortSpec] = {c.cohort_id: c for c in COHORTS}


def resolve_data_path(spec: CohortSpec) -> str | None:
    """Return the configured data path for a cohort, or None if unset.

    Reads ``spec.env_vars`` in order; the first environment variable that is set
    and non-empty wins. Never returns a hardcoded path -- if nothing is
    configured the caller reports the cohort as unavailable (and the endpoint
    fails closed rather than auditing a guessed path).
    """
    for var in spec.env_vars:
        val = os.environ.get(var)
        if val:
            return val
    return None
