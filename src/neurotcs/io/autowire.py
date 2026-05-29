"""Auto-wire wide-format measurement sheets to production range packs.

NeuroTCS range packs audit measurement VALUES (e.g. MMSE total must be 0-30).
They consume LONG-format data (measurement_name / value / unit columns). Real
exports are usually WIDE (one column per measurement). This module bridges that
gap WITHOUT guessing:

  * a wide column is wired only when its name resolves to exactly ONE canonical
    production measurement (exact canonical name, or a curated alias) AND its
    unit is compatible with the pack's declared unit;
  * every wiring decision is recorded; ambiguous, unit-mismatched, or
    unresolved columns are REFUSED (returned as `refusals`, surfaced in the
    coverage declaration) -- never wired on a guess.

This preserves NeuroTCS's no-silent-guess property while extending audit
coverage from staging-only to biomarker values. The alias table is functional
domain knowledge (column-naming conventions), NOT data tuned to any one file;
unit suffixes are read from the column name and checked against the pack, so a
cm^3 column can never be silently audited against an mm^3 bound.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import pandas as pd

from neurotcs.clinical_ranges import list_rangepacks, load_rangepack

# --- subject / visit column synonyms (same conventions as staging detection) ---
_PID_SYNONYMS = ("subject_id", "patient_id", "rid", "ptid", "usubjid",
                 "participant_id", "id")
_VISIT_SYNONYMS = ("visit", "visit_id", "viscode", "visitnum", "event_id",
                   "visit_code", "timepoint", "wave")


# Measurements SAFE to auto-wire: assay-independent, definitionally-bounded
# ordinal / cognitive / staging scales (e.g. MMSE 0-30, Braak 0-6). Their bounds
# are administrative scale limits, identical across cohorts and assays, so a
# name match is sufficient. Everything else -- fluid biomarkers, PET
# quantitation, volumetry, centiloid -- has ASSAY/SCALE-CALIBRATED bounds where a
# generically-named column cannot be certified to match the pack's calibration;
# auto-wiring those produces false positives (verified: 100% of rows flagged), so
# they are REFUSED and must be wired via an explicit mapping that asserts the
# assay/scale. This is the line that keeps auto-audit free of false alarms.
_SAFE_AUTOWIRE_MEASUREMENTS: frozenset[str] = frozenset({
    "mmse_total", "moca_total",
    "adas_cog_11_total", "adas_cog_13_total", "iadrs_total",
    "adcs_adl_total", "adcs_iadl_total",
    "cdr_sb_sum_boxes",
    "npiq_total_severity", "npiq_total_distress",
    "faq_total", "gds15_total", "upsit_total",
    "braak_nft_stage", "thal_amyloid_phase", "cerad_neuritic_plaque_score",
})


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _norm_unit(u: str | None) -> str:
    """Normalize unit strings so cm^3==cm3, pg/mL==pgml, ratio==suvr, etc."""
    if u is None:
        return ""
    x = re.sub(r"[^a-z0-9]", "", str(u).lower())
    # treat SUVR / ratio as the same dimensionless ratio family
    if x in ("ratio", "suvr"):
        return "ratio"
    return x


@lru_cache(maxsize=1)
def _production_inventory() -> dict[str, tuple[str, str]]:
    """canonical measurement_name -> (pack_id, RAW_unit), production packs only,
    and only names that map to EXACTLY one production pack (names shared by >1
    pack are dropped to avoid an ambiguous auto-wire).

    The RAW pack unit string is stored (not the normalized form) because the
    range auditor compares the submitted unit to ``measurement.unit`` by EXACT
    string equality. Emitting a normalized unit (e.g. 'pgml' for a 'pg/mL' pack)
    would trip a spurious unit_mismatch on every row. Normalization is applied
    only at the compatibility-check site, never to the emitted data."""
    seen: dict[str, list[tuple[str, str]]] = {}
    for p in list_rangepacks():
        if p["status"] != "production":
            continue
        pid = p["name"]
        rp = load_rangepack(pid).rangepack
        for m in rp.measurements:
            seen.setdefault(m.name, []).append((pid, m.unit))
    return {name: lst[0] for name, lst in seen.items() if len(lst) == 1}


# --- curated alias table: common WIDE column names -> canonical measurement ---
# Functional domain knowledge (naming conventions across ADNI / NACC / vendor
# exports), NOT values and NOT tuned to any single dataset. Only unambiguous,
# high-confidence aliases belong here. Unit is still checked separately.
_ALIASES: dict[str, str] = {
    # cognitive
    "mmse": "mmse_total", "mmsetotal": "mmse_total", "mmsescore": "mmse_total",
    "moca": "moca_total", "mocatotal": "moca_total",
    "cdrglobal": "cdr_global_score", "cdrgl": "cdr_global_score",
    "cdrsob": "cdr_sb_sum_boxes", "cdrsb": "cdr_sb_sum_boxes",
    "adascog13": "adas_cog_13_total", "adas13": "adas_cog_13_total",
    "adascog11": "adas_cog_11_total", "adas11": "adas_cog_11_total",
    "npiqtotal": "npiq_total_severity", "npiq": "npiq_total_severity",
    "faqtotal": "faq_total", "faq": "faq_total",
    "gds15": "gds15_total", "gds15total": "gds15_total",
    # MRI volumetrics (unit suffix is checked; mm3 vs cm3 caught downstream)
    "hippocampaltotalmm3": "hippocampal_volume_total_mm3",
    "hippocampusvolumetotalmm3": "hippocampal_volume_total_mm3",
    "etivmm3": None,  # explicit: eTIV in cm^3 only; mm3 column refused
    "etivcm3": "total_intracranial_volume_eTIV_cm3",
    "totalintracranialvolumeetivcm3": "total_intracranial_volume_eTIV_cm3",
    "meancorticalthicknessmm": "mean_cortical_thickness_mm",
    "corticalthicknessmm": "mean_cortical_thickness_mm",
    "wmhtotalvolumeml": "wmh_total_volume_ml",
    "wmhtotalml": "wmh_total_volume_ml",
    "fazekascombined": "fazekas_combined_score",
    "fazekascombinedscore": "fazekas_combined_score",
    # amyloid PET
    "amyloidcentiloid": "centiloid_value", "centiloid": "centiloid_value",
    "centiloidvalue": "centiloid_value",
    # tau PET
    "braakstage": "braak_nft_stage",
    # FDG PET
    "fdgdosembq": "fdg_pet_dose_mbq",
    "fdguptakemin": "fdg_pet_uptake_time_min",
    "fdgprecuneussuvr": "fdg_pet_precuneus_suvr_cerebellum",
    "fdgposteriorcingulatesuvr": "fdg_pet_posterior_cingulate_suvr_cerebellum",
    # fluid biomarkers
    "plasmaptau217pgml": "plasma_ptau217_pgml",
    "plasmanflpgml": "plasma_nfl_pgml",
    "csfptau181pgml": "csf_ptau181_pgml_lumipulse",
    "csfabeta4240ratio": "csf_abeta42_40_ratio_lumipulse",
}

# unit token that may be embedded as a column-name suffix -> normalized unit
_UNIT_SUFFIXES = (
    ("cm3", "cm3"), ("cm^3", "cm3"),
    ("mm3", "mm3"), ("mm^3", "mm3"),
    ("pgml", "pgml"), ("pg/ml", "pgml"),
    ("mbq", "mbq"),
    ("ml", "ml"),
    ("mm", "mm"),
    ("min", "min"),
    ("suvr", "ratio"),
)


def _column_unit_suffix(col: str) -> str | None:
    n = _norm(col)
    for suf, norm in _UNIT_SUFFIXES:
        if n.endswith(_norm(suf)):
            return norm
    return None


def _resolve_column(col: str) -> str | None:
    """Resolve a wide column name to a canonical production measurement name, or
    None if it does not confidently match exactly one."""
    inv = _production_inventory()
    n = _norm(col)
    if col in inv:                       # exact canonical name
        return col
    for cand in inv:                     # exact match on normalized canonical
        if _norm(cand) == n:
            return cand
    alias = _ALIASES.get(n)
    if alias is None:
        return None
    return alias if alias in inv else None


def _find_col(cols: list[str], synonyms: tuple[str, ...]) -> str | None:
    norm_map = {_norm(c): c for c in cols}
    for s in synonyms:
        if _norm(s) in norm_map:
            return norm_map[_norm(s)]
    return None


def autowire_ranges(
    tables: dict[str, pd.DataFrame],
    already_wired_sheets: set[str],
    confirm_assays: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], list[str], list[str]]:
    """Return (ranges_specs, extra_long_tables, decisions, refusals).

    For each sheet NOT already wired to staging, resolve its value columns to
    production pack measurements. Columns that resolve cleanly (name + unit) are
    melted per-pack into a synthetic LONG table; a ranges spec is emitted for it.
    Unresolved / unit-mismatched columns are reported in `refusals`.

    Assay/scale-calibrated biomarkers (CSF/plasma p-tau, NfL, centiloid,
    volumetry, FDG, ...) are REFUSED by default: a column name cannot certify
    that the data was produced on the same assay/scale the pack's bounds encode,
    and auto-wiring on a guess produces false flags. They are audited only when
    ``confirm_assays=True`` -- the operator's explicit assertion that the data
    was measured on the assay/scale the matched pack encodes (CLI:
    ``--confirm-assays``). This keeps the zero-config default fail-closed while
    giving every user a one-flag path to the assay packs, with the assertion
    recorded in the decision log. A unit mismatch is still refused even under
    ``confirm_assays`` -- that is a hard incompatibility, not an assay question.
    """
    inv = _production_inventory()
    ranges_specs: list[dict[str, Any]] = []
    extra_tables: dict[str, pd.DataFrame] = {}
    decisions: list[str] = []
    refusals: list[str] = []
    wired_source_sheets: set[str] = set()
    assay_confirmed_cols: set[str] = set()

    for sheet, df in tables.items():
        if sheet in already_wired_sheets:
            continue
        cols = [str(c) for c in df.columns]
        pid = _find_col(cols, _PID_SYNONYMS)
        vis = _find_col(cols, _VISIT_SYNONYMS)
        if pid is None or vis is None:
            continue  # not a per-subject measurement sheet; coverage declares it

        # group resolvable value columns by target pack
        by_pack: dict[str, list[tuple[str, str, str]]] = {}
        for c in cols:
            if c in (pid, vis):
                continue
            canon = _resolve_column(c)
            if canon is None:
                continue  # unresolved -> left to coverage (not a refusal per-col)
            pack_id, pack_unit = inv[canon]
            is_assay = canon not in _SAFE_AUTOWIRE_MEASUREMENTS
            if is_assay and not confirm_assays:
                refusals.append(
                    f"{sheet}.{c}: resolves to {canon} ({pack_id}) but that is an "
                    f"assay/scale-calibrated biomarker -- NOT auto-wired (bounds "
                    f"are calibration-specific; a column name cannot certify the "
                    f"assay). Re-run with --confirm-assays (asserting your data "
                    f"was measured on the assay/scale this pack encodes) to audit "
                    f"it, or provide an explicit 'ranges' mapping."
                )
                continue
            col_unit = _column_unit_suffix(c)
            if col_unit is not None and col_unit != _norm_unit(pack_unit):
                refusals.append(
                    f"{sheet}.{c}: resolves to {canon} (pack expects "
                    f"unit '{pack_unit}') but column unit looks like '{col_unit}'"
                    f" -- NOT wired (unit mismatch; provide explicit mapping)."
                )
                continue
            if is_assay:
                assay_confirmed_cols.add(f"{sheet}.{c}")
            by_pack.setdefault(pack_id, []).append((c, canon, pack_unit))

        for pack_id, items in by_pack.items():
            long_rows = []
            for col, canon, unit in items:
                sub = df[[pid, vis, col]].copy()
                sub.columns = ["patient_id", "visit_id", "value"]
                sub["measurement_name"] = canon
                sub["unit"] = unit
                long_rows.append(sub)
            long_df = pd.concat(long_rows, ignore_index=True)
            long_df = long_df.dropna(subset=["value"])
            wired_source_sheets.add(sheet)
            syn_sheet = f"__autowired__{sheet}__{_norm(pack_id)}"
            extra_tables[syn_sheet] = long_df
            ranges_specs.append({
                "sheet": syn_sheet, "pack": pack_id,
                "patient_id": "patient_id", "visit_id": "visit_id",
                "measurement_name": "measurement_name",
                "value": "value", "unit": "unit",
            })
            confirmed = [c for c, _, _ in items
                         if f"{sheet}.{c}" in assay_confirmed_cols]
            note = "  [assay-confirmed by operator (--confirm-assays)]" if confirmed else ""
            decisions.append(
                f"{sheet} -> {pack_id}: "
                + ", ".join(f"{c}={canon}" for c, canon, _ in items)
                + note
            )

    return ranges_specs, extra_tables, decisions, refusals, wired_source_sheets
