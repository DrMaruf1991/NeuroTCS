"""The top-level CLI must support --version (release polish, v1.82.6): a bare
`neurotcs` requires a subcommand, but `--version` must intercept and exit 0 with
the package version -- both for user convenience and so CI smoke-tests have a
stable zero-exit invocation.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from neurotcs import __version__


def test_version_flag_exits_zero_and_prints_version():
    r = subprocess.run(
        [sys.executable, "-m", "neurotcs", "--version"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"--version should exit 0, got {r.returncode}: {r.stderr}"
    out = (r.stdout + r.stderr)
    assert __version__ in out, f"--version output should contain {__version__}: {out!r}"


def test_version_flag_via_parser():
    from neurotcs.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    # argparse 'version' action exits 0
    assert exc.value.code == 0
