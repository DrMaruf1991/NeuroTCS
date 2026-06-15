"""A4 fix (v1.78.0): staging-column matcher is separator-insensitive (Pass 2),
mirroring the measurement matcher, while Pass 1 stays byte-identical so existing
audit_ids never drift. Fail-closed: ambiguous normalized matches refuse.

Two levels of proof:
  * unit -- the _norm_col/_norm parity invariant and the ambiguity guard, which
    are only visible at the function level;
  * end-to-end -- a separator-less staging column auto-maps through the real
    _scaffold_mapping path a user actually hits (mirrors test_v138 style).
"""
from __future__ import annotations

import pandas as pd

from neurotcs.cli import (
    _COL_SYN_STATE_CLINICAL,
    _best_column,
    _norm_col,
    _scaffold_mapping,
)
from neurotcs.io import describe_tables
from neurotcs.io.autowire import _norm


# --------------------------------------------------------------------------- #
# 1. Parity invariant: cli._norm_col MUST equal autowire._norm (anti-rot gate).
#    If anyone changes one normalizer without the other, this test goes red.
# --------------------------------------------------------------------------- #
def test_norm_col_matches_autowire_norm():
    samples = [
        "DX_STATUS", "dx-status", "DXSTATUS", "Clinical State", "RID",
        "a+t-n+", "biological_stage_atn", "visit.date", "", "___",
        "MixedCase_123", "tab\tsep", "  spaces  ", "UPPER", "dots...here",
    ]
    for s in samples:
        assert _norm_col(s) == _norm(s), f"normalizer divergence on {s!r}"


# --------------------------------------------------------------------------- #
# 2. Pass 1 unchanged: an exact (case-insensitive) match maps as it always did.
# --------------------------------------------------------------------------- #
def test_pass1_exact_match_unchanged():
    out = _best_column(["RID", "VISCODE", "dx_status"],
                       _COL_SYN_STATE_CLINICAL, "state")
    assert out == "dx_status"


# --------------------------------------------------------------------------- #
# 3. Pass 1 precedence: when BOTH an exact match and a separator-variant exist,
#    the exact Pass-1 hit wins; Pass 2 never runs.
# --------------------------------------------------------------------------- #
def test_pass1_precedence_over_pass2():
    # "DX_STATUS".lower() == "dx_status" == synonym -> Pass 1 returns it.
    out = _best_column(["dxstatus", "DX_STATUS"],
                       _COL_SYN_STATE_CLINICAL, "state")
    assert out == "DX_STATUS"


# --------------------------------------------------------------------------- #
# 4. Fail-closed guard: no exact match, and the matched synonym normalizes onto
#    >1 column -> refuse rather than guess.
# --------------------------------------------------------------------------- #
def test_pass2_pure_ambiguity_refuses():
    # Both "dxstatus" and "DXSTATUS" normalize to "dxstatus"; synonym dx_status
    # (norm "dxstatus") hits both -> ambiguous -> refuse.
    out = _best_column(["dxstatus", "DXSTATUS"],
                       _COL_SYN_STATE_CLINICAL, "state",
                       return_none_on_miss=True)
    assert out is None


# --------------------------------------------------------------------------- #
# 5. Pass 2 win: a single separator-less staging column NOW maps (the fix),
#    proven end-to-end through the real _scaffold_mapping path.
#    Before the fix this returned <FILL:state>; after, it maps to DXSTATUS.
# --------------------------------------------------------------------------- #
def test_dxstatus_auto_maps_end_to_end():
    tables = {
        "AUDIT_CLINICAL": pd.DataFrame({
            "RID": ["1", "1", "2"],
            "VISCODE": ["bl", "m12", "bl"],
            "EXAMDATE": ["2020-01-01", "2021-01-01", "2020-06-01"],
            "DXSTATUS": ["CN", "MCI", "CN"],
        }),
    }
    spec = _scaffold_mapping(describe_tables(tables))["clinical"]
    assert spec["state"] == "DXSTATUS"
    assert not any(
        isinstance(v, str) and v.startswith("<FILL:") for v in spec.values()
    )
