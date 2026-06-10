"""Exit-code contract for scripts/verify_citations.py.

The verifier is the gate that stops a Marras/Hayden-class citation defect
(wrong PMID/DOI) from shipping. A prior version returned 0 even when it
detected a mismatch -- a fail-OPEN bug that made the gate unable to go red.
These tests lock the documented contract so that can never silently recur:

  exit 0  = ran, all resolved citations matched (or only allowlist hits)
  exit 1  = at least one mismatch (build must fail)
  exit 2  = could not verify (total network/index outage; not a clean pass)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "verify_citations.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_citations", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # register before exec so dataclasses can resolve the module
    sys.modules["verify_citations"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_offline_mode_runs_and_exits_zero():
    mod = _load()
    rc = mod.main(["--offline"])
    assert rc == 0


def test_mismatch_returns_exit_1(monkeypatch):
    """A single detected mismatch MUST fail the build (exit 1)."""
    mod = _load()
    fake_ref = mod.CitationRef(
        file_path=(_REPO / "fake.yaml"), line=1, pmid="12345678",
        doi="10.1000/fake", context="[anchor] Some Journal, Smith 2020")

    # One ref to check; resolvers return a record whose journal/author won't
    # match the context -> find_mismatches yields a Mismatch.
    monkeypatch.setattr(mod, "scan_rulepack_yamls", lambda: [fake_ref])
    monkeypatch.setattr(mod, "scan_transcription_audits", lambda: [])
    monkeypatch.setattr(mod, "_load_cache", lambda: {})
    monkeypatch.setattr(mod, "_save_cache", lambda c: None)

    rec = mod.ResolverRecord(
        source="crossref", pmid=None, doi="10.1000/fake",
        journal="Completely Different Journal", title="X", year=2020,
        first_page="1", authors_last_names=["Nomatch"])
    monkeypatch.setattr(mod, "resolve_crossref", lambda doi: rec)
    monkeypatch.setattr(mod, "resolve_eutils", lambda pmid: None)

    rc = mod.main([])
    assert rc == 1, "a detected mismatch must return exit 1, never 0"


def test_clean_match_returns_exit_0(monkeypatch):
    """When the resolved metadata is consistent with the context, exit 0."""
    mod = _load()
    fake_ref = mod.CitationRef(
        file_path=(_REPO / "ok.yaml"), line=1, pmid=None,
        doi="10.1000/ok", context="[anchor] Nature Medicine, Ossenkoppele 2022")
    monkeypatch.setattr(mod, "scan_rulepack_yamls", lambda: [fake_ref])
    monkeypatch.setattr(mod, "scan_transcription_audits", lambda: [])
    monkeypatch.setattr(mod, "_load_cache", lambda: {})
    monkeypatch.setattr(mod, "_save_cache", lambda c: None)
    rec = mod.ResolverRecord(
        source="crossref", pmid=None, doi="10.1000/ok",
        journal="Nature Medicine", title="X", year=2022,
        first_page="1", authors_last_names=["Ossenkoppele"])
    monkeypatch.setattr(mod, "resolve_crossref", lambda doi: rec)
    monkeypatch.setattr(mod, "resolve_eutils", lambda pmid: None)
    rc = mod.main([])
    assert rc == 0


def test_total_outage_returns_exit_2(monkeypatch):
    """If every resolvable citation fails to resolve (outage), return 2 --
    'could not verify' is not the same as 'verified clean'."""
    mod = _load()
    fake_ref = mod.CitationRef(
        file_path=(_REPO / "x.yaml"), line=1, pmid="999", doi="10.1000/down",
        context="[anchor] whatever")
    monkeypatch.setattr(mod, "scan_rulepack_yamls", lambda: [fake_ref])
    monkeypatch.setattr(mod, "scan_transcription_audits", lambda: [])
    monkeypatch.setattr(mod, "_load_cache", lambda: {})
    monkeypatch.setattr(mod, "_save_cache", lambda c: None)
    # Both resolvers return None (network down).
    monkeypatch.setattr(mod, "resolve_crossref", lambda doi: None)
    monkeypatch.setattr(mod, "resolve_eutils", lambda pmid: None)
    rc = mod.main([])
    assert rc == 2
