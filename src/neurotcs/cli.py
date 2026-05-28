"""NeuroTCS command-line interface.

Verbs:
  describe <file> [--emit-mapping PATH]   inspect a dataset file; scaffold a mapping
  audit    <file> --mapping map.json ...  audit a dataset, emit a signed bundle
  verify   <bundle.json>                  re-verify a signed bundle (tamper check)

Exit codes (stable contract -- safe to branch on in pipelines):
  0  CLEAN              audit ran, no flags / bundle verified
  1  FLAGS_PRESENT      audit ran, flags found
  2  (argparse usage)   bad command-line arguments
  3  INCOMPLETE_REFUSED auditor refused (e.g. unrecorded skip)
  4  INPUT_ERROR        file/mapping problem (missing, unreadable, unmapped)
  5  VERIFY_FAILED      bundle failed verification (tampered / malformed)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from neurotcs import (
    BundleVerificationError,
    build_bundle,
    fingerprint_file,
    render_report,
    run_full_audit,
    verify_bundle,
)
from neurotcs.io import (
    PdfExtractionError,
    UnsupportedFormatError,
    describe_tables,
    read_tables,
    tables_to_submission,
)
from neurotcs.report import bundle_to_pdf, bundle_to_svg, flags_to_csv

EXIT_CLEAN = 0
EXIT_FLAGS = 1
EXIT_REFUSED = 3
EXIT_INPUT = 4
EXIT_VERIFY = 5

_STAGING_COLS = ("subject_id", "visit", "visit_date", "state")
_RANGE_COLS = ("patient_id", "visit_id", "measurement_name", "value", "unit")


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _load_tables(path: str, allow_pdf: bool) -> dict[str, Any] | None:
    try:
        return read_tables(path, allow_pdf=allow_pdf)
    except (FileNotFoundError, UnsupportedFormatError, PdfExtractionError) as e:
        _err(str(e))
        return None


# --------------------------------------------------------------------------- #
# describe
# --------------------------------------------------------------------------- #
def cmd_describe(args: argparse.Namespace) -> int:
    tables = _load_tables(args.file, args.allow_pdf)
    if tables is None:
        return EXIT_INPUT
    desc = describe_tables(tables)
    print(f"# {args.file}")
    for name, info in desc.items():
        print(f"  sheet '{name}': {info['shape'][0]} rows x {info['shape'][1]} cols")
        print(f"    columns: {info['columns']}")

    if args.emit_mapping is not None:
        mapping = _scaffold_mapping(desc)
        out = Path(args.emit_mapping)
        out.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        print(f"\nwrote mapping template -> {out}")
        print("Edit the '<FILL:...>' placeholders, then: "
              f"neurotcs audit {args.file} --mapping {out}")
    return EXIT_CLEAN


def _match(columns: list[str], canonical: str) -> str:
    """Return the column if its canonical name is present, else a FILL placeholder."""
    return canonical if canonical in columns else f"<FILL:{canonical}>"


def _scaffold_mapping(desc: dict[str, Any]) -> dict[str, Any]:
    """Build a mapping skeleton from detected sheets. Pre-fills columns whose
    canonical name is present; everything else is a placeholder to review.
    The auditor never consumes placeholders -- it fails closed until you edit them.
    """
    sheets = list(desc.keys())
    first = sheets[0] if sheets else "<FILL:sheet>"
    cols0 = desc.get(first, {}).get("columns", []) if sheets else []
    mapping: dict[str, Any] = {
        "_detected": desc,  # reference only; ignored by the auditor
        "clinical": {"sheet": first,
                     **{c: _match(cols0, c) for c in _STAGING_COLS}},
    }
    # offer a biological skeleton only if a second sheet exists
    if len(sheets) > 1:
        cols1 = desc[sheets[1]]["columns"]
        mapping["biological"] = {"sheet": sheets[1],
                                 **{c: _match(cols1, c) for c in _STAGING_COLS}}
    # ranges: empty by default so a fully-mapped staging audit is not blocked by
    # an unused example. A reference example lives under an ignored '_' key.
    mapping["ranges"] = []
    mapping["_ranges_example"] = {
        "sheet": "<FILL:measurements_sheet>",
        "pack": "<FILL:domain/pack_name>",
        **{c: f"<FILL:{c}>" for c in _RANGE_COLS},
    }
    return mapping


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def _clean_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """Drop the reference '_detected' block and any unfilled placeholder sections."""
    m = {k: v for k, v in mapping.items() if not k.startswith("_")}
    # drop a section if it still has FILL placeholders (so a half-edited template
    # fails loudly with a clear message rather than silently auditing nothing)
    return m


def _has_placeholder(obj: Any) -> bool:
    if isinstance(obj, str):
        return obj.startswith("<FILL:")
    if isinstance(obj, dict):
        return any(_has_placeholder(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_placeholder(v) for v in obj)
    return False


def cmd_audit(args: argparse.Namespace) -> int:
    tables = _load_tables(args.file, args.allow_pdf)
    if tables is None:
        return EXIT_INPUT

    try:
        mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    except FileNotFoundError:
        _err(f"mapping file not found: {args.mapping}. Generate one with: "
             f"neurotcs describe {args.file} --emit-mapping mapping.json")
        return EXIT_INPUT
    except json.JSONDecodeError as e:
        _err(f"mapping file is not valid JSON: {e}")
        return EXIT_INPUT

    mapping = _clean_mapping(mapping)
    if _has_placeholder(mapping):
        _err("mapping still contains <FILL:...> placeholders -- edit them before "
             "auditing (the auditor will not guess column names).")
        return EXIT_INPUT

    try:
        submission = tables_to_submission(tables, mapping)
    except (ValueError, KeyError) as e:
        _err(f"mapping does not match the data: {e}")
        return EXIT_INPUT

    result = run_full_audit(submission)
    try:
        fp = fingerprint_file(args.file)
        bundle = build_bundle(result, input_fingerprint=fp,
                              input_fingerprint_kind="raw_file_sha256")
    except Exception as e:  # noqa: BLE001 - surface any build failure cleanly
        _err(f"failed to build bundle: {e}")
        return EXIT_INPUT

    # always write the signed artifact of record + the text report
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.file).stem
    (outdir / f"{stem}.bundle.json").write_text(
        json.dumps(bundle, indent=2), encoding="utf-8")
    (outdir / f"{stem}.report.txt").write_text(
        render_report(bundle, use_symbols=True), encoding="utf-8")
    if args.csv:
        (outdir / f"{stem}.flags.csv").write_text(flags_to_csv(bundle), encoding="utf-8")
    if args.svg:
        (outdir / f"{stem}.summary.svg").write_text(bundle_to_svg(bundle), encoding="utf-8")
    if args.pdf:
        bundle_to_pdf(bundle, outdir / f"{stem}.report.pdf")

    core = bundle["neurotcs_bundle"]["deterministic_core"]
    status = core.get("status", "UNKNOWN")
    if not args.quiet:
        _print_summary(bundle, outdir, stem, args)

    if status == "INCOMPLETE_REFUSED":
        return EXIT_REFUSED
    if status == "FLAGS_PRESENT":
        return EXIT_FLAGS
    return EXIT_CLEAN


def _print_summary(bundle: dict[str, Any], outdir: Path, stem: str,
                   args: argparse.Namespace) -> None:
    core = bundle["neurotcs_bundle"]["deterministic_core"]
    sev = core.get("severity_counts", {})
    print(f"status: {core.get('status')}")
    for ax in core.get("axes", []):
        lo, hi = ax.get("ctcs_ci_95_low"), ax.get("ctcs_ci_95_high")
        ci = f" [95% CI {lo}-{hi}]" if lo is not None and hi is not None else ""
        print(f"  {ax['axis']}: cTCS {ax['ctcs']}{ci}  "
              f"({ax['n_flagged']}/{ax['n_transitions']} flagged)")
    print(f"severity: impossible {sev.get('impossible', 0)} / "
          f"implausible {sev.get('implausible', 0)} / "
          f"informational {sev.get('informational', 0)}")
    print(f"bundle:   {outdir / (stem + '.bundle.json')}")
    print(f"report:   {outdir / (stem + '.report.txt')}")
    if args.csv:
        print(f"flags:    {outdir / (stem + '.flags.csv')}")
    if args.svg:
        print(f"svg:      {outdir / (stem + '.summary.svg')}")
    if args.pdf:
        print(f"pdf:      {outdir / (stem + '.report.pdf')}")


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #
def cmd_verify(args: argparse.Namespace) -> int:
    try:
        bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    except FileNotFoundError:
        _err(f"bundle not found: {args.bundle}")
        return EXIT_INPUT
    except json.JSONDecodeError as e:
        _err(f"bundle is not valid JSON: {e}")
        return EXIT_INPUT
    try:
        ok = verify_bundle(bundle)
    except BundleVerificationError as e:
        print(f"VERIFY FAILED: {e}")
        return EXIT_VERIFY
    except (KeyError, TypeError) as e:
        _err(f"not a NeuroTCS bundle: {e}")
        return EXIT_VERIFY
    if ok:
        bid = bundle["neurotcs_bundle"].get("bundle_id", "")
        print(f"VERIFIED OK  bundle_id {str(bid)[:24]}...")
        return EXIT_CLEAN
    print("VERIFY FAILED")
    return EXIT_VERIFY


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="neurotcs",
        description="NeuroTCS - fail-closed clinical trajectory auditor.",
        epilog="For low-level single-axis audits with bootstrap/prior tuning, "
               "see the 'neurotcs-audit' command.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("describe", help="inspect a dataset file; scaffold a mapping")
    d.add_argument("file")
    d.add_argument("--emit-mapping", metavar="PATH", default=None,
                   help="write a mapping template to PATH")
    d.add_argument("--allow-pdf", action="store_true",
                   help="enable best-effort PDF table extraction")
    d.set_defaults(func=cmd_describe)

    a = sub.add_parser("audit", help="audit a dataset and emit a signed bundle")
    a.add_argument("file")
    a.add_argument("--mapping", required=True, help="mapping JSON (see 'describe --emit-mapping')")
    a.add_argument("-o", "--outdir", default="neurotcs_out", help="output directory")
    a.add_argument("--csv", action="store_true", help="also write flags CSV")
    a.add_argument("--svg", action="store_true", help="also write summary SVG")
    a.add_argument("--pdf", action="store_true", help="also write PDF report")
    a.add_argument("--quiet", action="store_true", help="suppress the stdout summary")
    a.add_argument("--allow-pdf", action="store_true",
                   help="enable best-effort PDF table extraction")
    a.set_defaults(func=cmd_audit)

    v = sub.add_parser("verify", help="re-verify a signed bundle")
    v.add_argument("bundle")
    v.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
