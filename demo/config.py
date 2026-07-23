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
from pathlib import Path


def _load_dotenv_if_present() -> None:
    """Load ``demo/.env`` (if it exists) into the environment for LOCAL dev.

    Makes the documented ".env" workflow actually work: both pytest and uvicorn
    pick up the cohort data paths without the caller having to export env vars by
    hand -- which matters on Windows and when a path contains spaces (e.g.
    ``G:/NeuroTCS data/...``), where shell quoting is easy to get wrong.

    Real environment variables ALWAYS win (``override=False``): on Azure the App
    Service Application Settings provide the paths and there is no ``.env`` file,
    so this is a silent no-op in production. Best-effort: if python-dotenv is not
    installed, we simply skip and fall back to os.environ.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_dotenv_if_present()


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
    # Locked reproducibility metadata (from tests/audit_core/test_real_*_audit.py).
    # Used to render the "locked reference" result when this host has no DUA data
    # to recompute -- the real, previously-reproduced values, not a live run.
    # ``locked_audit_id`` is None for cohorts whose invariant test does not pin one
    # (A4 locks cTCS/counts only); CI endpoints are None where the test does not
    # publish them.
    locked_audit_id: str | None = None
    locked_ci_low: float | None = None
    locked_ci_high: float | None = None


# cTCS parity tolerance (framework standard) and EXACT count matching.
CTCS_ABS_TOL = 0.0005

# Rule pack + anchor citation shared by every AD cohort audit (NIA-AA 2018).
# The engine attaches these to every flag; the demo surfaces them so the
# "locked reference" view (shown when this host has no DUA data to recompute)
# carries the same citation the live audit would.
RULEPACK_ID = "ad/niaaa_2018@1.3.0"
CITATION_PMID = "29653606"
CITATION_DOI = "10.1016/j.jalz.2018.02.018"

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
        locked_audit_id=(
            "58329c656e5ae14c8c6af496a6b526c2f93d317379ba3ffd145776e1cfcf07a9"
        ),
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
        locked_audit_id=(
            "92df5429ed8439f84a9a65d18b1c489a2b50107facc08e3e59538948c9ad6478"
        ),
        locked_ci_low=0.9902,
        locked_ci_high=0.9964,
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
        locked_audit_id=(
            "7a973f7b57a91f7cf0af796fd9f69552e14b57aa91f4241fabd5262436588f08"
        ),
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
        locked_audit_id=(
            "abda26cb4f77c4f5c7644b421b459b79dfa5caf58f32d60860736c6a2c9ee57f"
        ),
        locked_ci_low=0.9715,
        locked_ci_high=0.9937,
    ),
)

COHORTS_BY_ID: dict[str, CohortSpec] = {c.cohort_id: c for c in COHORTS}


def resolve_data_path(spec: CohortSpec) -> str | None:
    """Return the configured data path for a cohort, or None if unset.

    Reads ``spec.env_vars`` in order; the first environment variable that is set
    and non-empty wins. Never returns a hardcoded path -- if nothing is
    configured the caller reports the cohort as unavailable (and the endpoint
    fails closed rather than auditing a guessed path).

    NOTE: this only reports what is *configured*; it does NOT check that the path
    exists. Use ``data_available`` to decide whether a cohort can actually be
    audited on this host -- "configured" and "present" are different things.
    """
    for var in spec.env_vars:
        val = os.environ.get(var)
        if val:
            return val
    return None


def data_available(spec: CohortSpec) -> bool:
    """True only if the cohort's data path is configured AND present on this host.

    THE canonical definition of "this cohort can be audited here", used by both
    the /api/cohorts ``available`` field and the parity test's skip gate, so the
    two can never diverge. A path that is set but missing (e.g. a .env carried
    over from another machine, or an Azure app-setting pointing at an unmounted
    share) is NOT available: reporting it as available would enable the UI's Run
    button and then fail at click time with a 503. Directories (MIRIAD) and files
    both satisfy ``Path.exists()``.
    """
    path = resolve_data_path(spec)
    return bool(path and Path(path).exists())
