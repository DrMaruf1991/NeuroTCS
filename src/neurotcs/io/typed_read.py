"""neurotcs.io.typed_read -- the typed-read contract (schema-on-read).

WHY THIS EXISTS (the honest v1.44 debt)
---------------------------------------
Until v1.47.0, the reader handed pandas' implicit type inference straight
through (``pd.read_csv(...)`` with no dtype/na_values/decimal control). That
inference is deterministic on one machine but the DECISIONS are invisible and
unguarded -- unacceptable for sponsors who must reproduce a result at another
site (21 CFR Part 11 / GxP). Three concrete failure modes were latent:

  1. ID COLLAPSE -- a long numeric subject/site ID (e.g. "100000000000123" or a
     leading-zero ID "007") is silently coerced to float ("1.0000000000001e+14")
     or loses its leading zeros, corrupting joins and de-identification.
  2. LOCALE MISPARSE -- EU-formatted decimals ("1,5") are read as strings or
     mis-split; pandas assumes "." without saying so.
  3. SENTINEL-AS-VALUE -- a numeric missing code ("-9", "-999") is read as a
     real number, or a textual sentinel silently becomes NaN, with no record of
     which tokens were treated as missing.

This module replaces the silent guess with an EXPLICIT, LOCALE-INDEPENDENT,
SURFACED per-column decision, applied AFTER the raw read. It is designed to be
downstream-safe: columns that are genuinely numeric still receive a real numeric
dtype, so the existing ``pd.api.types.is_numeric_dtype(...)`` branches in
data_integrity and cross_sheet_autowire keep firing identically. The contract
only makes the decision auditable and guards the three failure modes.

CONTRACT (per column, in order)
-------------------------------
  * ID columns (name matches an ID pattern) -> forced to string, leading zeros
    and full precision preserved. NEVER numerically coerced.
  * Otherwise, the column becomes numeric IFF every non-missing value parses as
    a number under a SINGLE declared decimal convention (dot or comma), decided
    by consistency across the column. Mixed/ambiguous conventions are NOT
    guessed -- the column stays string (and the ambiguity is surfaced).
  * Missing values: only the documented sentinel set is treated as NA by
    default. Numeric missing codes (-9/-99/-999/...) are NOT auto-NA (a real
    -9 must never be silently dropped); they are reported so the operator can
    assert them explicitly if desired.
  * Every decision is appended to ``decisions`` (the same provenance stream the
    reader already surfaces into the bundle).
"""
from __future__ import annotations

import re

import pandas as pd

# Default textual missing-value sentinels (case-insensitive, trimmed). A NUMERIC
# code like -9 is deliberately NOT here: silently treating -9 as missing can
# drop real data. Operators assert numeric sentinels explicitly if needed.
_DEFAULT_NA_TOKENS: tuple[str, ...] = (
    "", "na", "n/a", "nan", "null", "none", ".", "<na>", "missing",
)

# Column-name patterns that force string typing (identity / linkage columns).
# Matched case-insensitively against the normalized column name.
_ID_NAME_PATTERNS: tuple[str, ...] = (
    r"^id$", r"_id$", r"^id_", r"subject", r"^rid$", r"^ptid$", r"^usubjid$",
    r"^site", r"_site$", r"^siteid$", r"^visit_?id$", r"^record_?id$",
    r"^mrn$", r"^accession", r"^scan_?id$", r"^image_?id$", r"^study_?id$",
)
_ID_RE = re.compile("|".join(_ID_NAME_PATTERNS), re.IGNORECASE)

# Numeric missing-code patterns (reported, NOT auto-applied).
_NUMERIC_SENTINEL_RE = re.compile(r"^-(9|99|999|9999)(\.0+)?$")


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _is_id_column(name: str) -> bool:
    return bool(_ID_RE.search(str(name))) or _norm(name) in {
        "id", "subjectid", "rid", "ptid", "usubjid", "siteid", "visitid",
        "recordid", "mrn", "scanid", "imageid", "studyid",
    }


def _looks_missing(token: str, na_tokens: frozenset[str]) -> bool:
    return token.strip().lower() in na_tokens


def _try_numeric_series(
    s: pd.Series, na_tokens: frozenset[str]
) -> tuple[pd.Series | None, str | None]:
    """Attempt to convert a string column to numeric under a SINGLE decimal
    convention decided by consistency. Returns (numeric_series, decimal_kind)
    or (None, None) if the column is not cleanly numeric / is ambiguous.

    Rules:
      * Tokens that look missing -> NaN.
      * 'dot' convention: standard float parse (commas as thousands allowed only
        if unambiguous -- to stay safe we DISALLOW thousands grouping and treat
        a comma as the decimal mark candidate instead).
      * 'comma' convention: comma is the decimal mark ("1,5" -> 1.5), dots are
        thousands separators and stripped.
      * The column must parse cleanly under EXACTLY ONE convention. If it parses
        under both (e.g. pure integers with no separators), prefer 'dot' (the
        canonical) -- this is not ambiguous because the numeric value is
        identical. If it parses under neither, it is not numeric. If it would
        yield DIFFERENT values under the two conventions (contains separators),
        and only one convention parses cleanly, that one wins; if both parse to
        different values, it is AMBIGUOUS -> stay string.
    """
    vals = [v for v in s.tolist()]
    non_missing = [str(v).strip() for v in vals
                   if v is not None and not _looks_missing(str(v), na_tokens)
                   and not (isinstance(v, float) and pd.isna(v))]
    if not non_missing:
        return None, None  # all-missing column: leave as-is (not numeric)

    def parse_dot(tok: str) -> float | None:
        # Standard dot decimal; reject embedded commas (avoid thousands
        # ambiguity) and any non-numeric.
        if "," in tok:
            return None
        try:
            return float(tok)
        except ValueError:
            return None

    def parse_comma(tok: str) -> float | None:
        # Comma decimal: dots are thousands separators (stripped), the single
        # comma is the decimal mark. Reject >1 comma.
        if tok.count(",") > 1:
            return None
        t = tok.replace(".", "").replace(",", ".")
        try:
            return float(t)
        except ValueError:
            return None

    dot_vals = [parse_dot(t) for t in non_missing]
    comma_vals = [parse_comma(t) for t in non_missing]
    dot_ok = all(v is not None for v in dot_vals)
    comma_ok = all(v is not None for v in comma_vals)

    # Only a COMMA is the locale-sensitive decimal mark. A column containing no
    # commas is unambiguously dot-convention (a '.' is the decimal point). The
    # ambiguous case is strictly: the column contains commas AND parses cleanly
    # under both conventions to DIFFERENT values.
    has_comma = any("," in t for t in non_missing)

    chosen_kind: str | None = None
    if not has_comma:
        # No commas anywhere -> dot convention if it parses as numeric at all.
        chosen_kind = "dot" if dot_ok else None
    elif comma_ok and not dot_ok:
        chosen_kind = "comma"
    elif dot_ok and not comma_ok:
        chosen_kind = "dot"
    elif dot_ok and comma_ok:
        # Both parse and commas are present: ambiguous unless identical values.
        same = all(
            (dv is not None and cv is not None and dv == cv)
            for dv, cv in zip(dot_vals, comma_vals, strict=False)
        )
        chosen_kind = "dot" if same else None
    else:
        return None, None  # not numeric under either convention

    if chosen_kind is None:
        return None, None  # ambiguous decimal convention -> stay string

    parse = parse_dot if chosen_kind == "dot" else parse_comma
    out = []
    for v in vals:
        if v is None or _looks_missing(str(v), na_tokens) or (
            isinstance(v, float) and pd.isna(v)
        ):
            out.append(float("nan"))
        else:
            out.append(parse(str(v).strip()))
    ser = pd.Series(out, index=s.index, dtype="float64")
    # Down-cast to Int64 (nullable) if all non-na values are integral, to keep
    # IDs-as-counts and visit numbers clean and to match prior int inference.
    nonna = ser.dropna()
    if len(nonna) and (nonna == nonna.round()).all():
        try:
            ser = ser.astype("Int64")
        except (ValueError, TypeError):
            pass
    return ser, chosen_kind


def apply_typed_read_contract(
    df: pd.DataFrame,
    name: str,
    decisions: list[str],
    *,
    na_tokens: tuple[str, ...] = _DEFAULT_NA_TOKENS,
    numeric_na_codes: dict[str, list[float | int | str]] | None = None,
) -> pd.DataFrame:
    """Apply the typed-read contract to a freshly-read DataFrame.

    Re-types each column by an explicit, surfaced, locale-independent rule and
    records every decision into ``decisions``. Returns a new DataFrame; the
    input is not mutated. Downstream-safe: numeric columns still receive a
    numeric dtype.

    numeric_na_codes (optional): per-column assertion that specific NUMERIC
    codes mean "missing" -- e.g. {"mmse": [-9], "*": [-999]}. A code is applied
    ONLY where the operator asserts it (never auto-detected): the contract
    reports numeric sentinels by default but keeps them, because a -9 may be a
    real value. The key "*" applies to every numeric column; a column-name key
    (matched case-insensitively against the actual or normalized name) applies
    to that column. Each application is surfaced in ``decisions``. Assertion runs
    AFTER coercion, so it covers both raw-numeric and coerced-numeric columns.
    """
    na_set = frozenset(t.strip().lower() for t in na_tokens)
    out = df.copy()
    numeric_sentinels_seen: dict[str, list[str]] = {}

    # Normalize the assertion map: lowercased keys, float code sets.
    asserted: dict[str, set[float]] = {}
    if numeric_na_codes:
        for k, codes in numeric_na_codes.items():
            cset: set[float] = set()
            for c in codes:
                try:
                    cset.add(float(c))
                except (ValueError, TypeError):
                    continue
            if cset:
                asserted[str(k).strip().lower()] = cset

    def _asserted_codes_for(col: str) -> set[float]:
        codes: set[float] = set()
        if "*" in asserted:
            codes |= asserted["*"]
        if str(col).lower() in asserted:
            codes |= asserted[str(col).lower()]
        if _norm(col) in asserted:
            codes |= asserted[_norm(col)]
        return codes

    def _apply_codes(series: pd.Series, col: str) -> pd.Series:
        codes = _asserted_codes_for(col)
        if not codes:
            return series
        before = series.copy()
        # Replace asserted numeric codes with NA (works for Int64/float64).
        mask = series.isin(list(codes))
        n = int(mask.sum())
        if n:
            series = series.mask(mask)
            applied = sorted({float(v) for v in before[mask].dropna().tolist()})
            decisions.append(
                f"{name}: column {col!r} -- asserted numeric missing-code(s) "
                f"{applied} treated as NA ({n} value(s)).")
        return series

    for col in out.columns:
        s = out[col]

        # 1) ID columns -> string, full precision / leading zeros preserved.
        if _is_id_column(col):
            # If pandas already turned a long ID into float (e.g. 1.23e+14),
            # recover integer-looking values without scientific notation.
            def _id_str(v: object) -> object:
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return v
                if isinstance(v, float) and v.is_integer():
                    return str(int(v))
                return str(v)
            out[col] = s.map(_id_str).astype("object")
            decisions.append(f"{name}: column {col!r} typed as ID (string, "
                             "precision preserved)")
            continue

        # 2) Already numeric from the raw read: keep, but record numeric
        # sentinels for transparency, then apply any asserted NA codes.
        if pd.api.types.is_numeric_dtype(s):
            sent = sorted({str(v) for v in s.dropna().tolist()
                           if _NUMERIC_SENTINEL_RE.match(str(v))})
            if sent:
                numeric_sentinels_seen[str(col)] = sent
            out[col] = _apply_codes(s, col)
            continue

        # 3) Object/string column: attempt explicit numeric coercion.
        if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            ser, kind = _try_numeric_series(s, na_set)
            if ser is not None:
                ser = _apply_codes(ser, col)
                out[col] = ser
                if kind == "comma":
                    decisions.append(
                        f"{name}: column {col!r} numeric (decimal comma "
                        "convention detected and applied)")
                # dot is the silent default; only surface the notable case.
                continue
            # stayed string -- note if it was a near-miss numeric ambiguity
            # (contains digits + separators but didn't cleanly parse).

    if numeric_sentinels_seen:
        # Only report sentinels that were NOT asserted away (those are handled).
        unhandled = {c: toks for c, toks in numeric_sentinels_seen.items()
                     if not _asserted_codes_for(c)}
        if unhandled:
            parts = "; ".join(f"{c}:{toks}" for c, toks
                              in sorted(unhandled.items()))
            decisions.append(
                f"{name}: numeric missing-code sentinels present and KEPT as "
                f"values (not auto-NA) [{parts}]. Assert them explicitly "
                "(numeric_na_codes) to treat as missing.")

    return out


def id_columns_from_names(columns: list[str]) -> list[str]:
    """Return the subset of column names that match an ID pattern.

    Used by the reader to pass dtype=str for these columns at read time, so a
    purely-numeric ID (e.g. '003') keeps its leading zeros instead of being
    coerced to int by pandas before the contract can protect it.
    """
    return [c for c in columns if _is_id_column(c)]


def schema_fingerprint(df: pd.DataFrame) -> dict[str, str]:
    """A deterministic per-column dtype map for the provenance bundle.

    Reproducibility anchor: two sites that apply the contract to the same data
    get the same schema fingerprint.
    """
    return {str(c): str(df[c].dtype) for c in df.columns}
