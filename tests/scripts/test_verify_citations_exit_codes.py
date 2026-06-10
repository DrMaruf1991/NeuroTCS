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
    """A single detected mismatch MUST fail the build (exit 1). We trigger a
    genuine wrong-identifier defect: the PMID and DOI resolve to different
    papers (different titles/authors), which the cross-resolver check flags."""
    mod = _load()
    fake_ref = mod.CitationRef(
        file_path=(_REPO / "fake.yaml"), line=1, pmid="12345678",
        doi="10.1000/fake", context="[anchor] some rule paraphrase")

    monkeypatch.setattr(mod, "scan_rulepack_yamls", lambda: [fake_ref])
    monkeypatch.setattr(mod, "scan_transcription_audits", lambda: [])
    monkeypatch.setattr(mod, "_load_cache", lambda: {})
    monkeypatch.setattr(mod, "_save_cache", lambda c: None)

    # DOI resolves to paper A; PMID resolves to a DIFFERENT paper B.
    cr = mod.ResolverRecord(
        source="crossref", pmid=None, doi="10.1000/fake",
        journal="Journal A", title="Paper A about amyloid", year=2024,
        first_page="1", authors_last_names=["Alpha"])
    eu = mod.ResolverRecord(
        source="eutils", pmid="12345678", doi="10.1000/other",
        journal="Journal B", title="Completely different paper B", year=2019,
        first_page="99", authors_last_names=["Beta"])
    monkeypatch.setattr(mod, "resolve_crossref", lambda doi: cr)
    monkeypatch.setattr(mod, "resolve_eutils", lambda pmid: eu)

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


class TestComparatorPrecision:
    """v1.77.0: the comparator must not false-flag correct citations (the YAML
    citation_text is a rule paraphrase, not a bibliographic claim) yet must
    still catch wrong-identifier (Hayden/Marras-class) defects via cross-resolver
    agreement. These lock the precision so the gate stays trustworthy."""

    def _mod(self):
        return _load()

    def test_legit_entity_encoded_journal_not_flagged(self):
        mod = self._mod()
        P = mod.PROJECT_ROOT
        ref = mod.CitationRef(
            file_path=P / "aa_2024.yaml", line=0, pmid="38934362",
            doi="10.1002/alz.13859",
            context="Jack 2024 Alzheimer's & Dementia 20:5143")
        cr = mod.ResolverRecord(
            source="crossref", pmid=None, doi="10.1002/alz.13859",
            journal="Alzheimer's &amp; Dementia", title="Revised criteria",
            year=2024, first_page="5143",
            authors_last_names=["Jack", "Andrews"])
        eu = mod.ResolverRecord(
            source="eutils", pmid="38934362", doi="10.1002/alz.13859",
            journal="Alzheimers Dement", title="Revised criteria",
            year=2024, first_page="5143",
            authors_last_names=["Jack", "Andrews"])
        assert mod.find_mismatches(ref, cr, eu) == []

    def test_wrong_pmid_glued_to_doi_is_flagged(self):
        """PMID resolves to paper X, DOI resolves to paper Y -> defect."""
        mod = self._mod()
        P = mod.PROJECT_ROOT
        ref = mod.CitationRef(
            file_path=P / "bio.yaml", line=0, pmid="38934362",
            doi="10.1002/alz.70997", context="La Joie 2025 (TRAC)")
        cr = mod.ResolverRecord(
            source="crossref", pmid=None, doi="10.1002/alz.70997",
            journal="Alzheimer's &amp; Dementia",
            title="Treatment-related amyloid clearance (TRAC)", year=2025,
            first_page="e70997", authors_last_names=["La Joie", "Cummings"])
        eu = mod.ResolverRecord(
            source="eutils", pmid="38934362", doi="10.1002/alz.13859",
            journal="Alzheimers Dement", title="Revised criteria", year=2024,
            first_page="5143", authors_last_names=["Jack", "Andrews"])
        flagged = mod.find_mismatches(ref, cr, eu)
        assert len(flagged) >= 1

    def test_paraphrase_without_journal_not_flagged(self):
        mod = self._mod()
        P = mod.PROJECT_ROOT
        ref = mod.CitationRef(
            file_path=P / "adni.yaml", line=0, pmid=None,
            doi="10.3389/fneur.2022.685636",
            context="SMC carries elevated progression hazard; admissible")
        cr = mod.ResolverRecord(
            source="crossref", pmid=None, doi="10.3389/fneur.2022.685636",
            journal="Frontiers in Neurology", title="t", year=2022,
            first_page="1", authors_last_names=["Lin"])
        assert mod.find_mismatches(ref, cr, None) == []

    def test_marras_class_text_names_conflicting_journal_flagged(self):
        mod = self._mod()
        P = mod.PROJECT_ROOT
        ref = mod.CitationRef(
            file_path=P / "x.yaml", line=0, pmid="12345", doi=None,
            context="Marras 2002, Movement Disorders 17(3):427")
        eu = mod.ResolverRecord(
            source="eutils", pmid="12345", doi=None, journal="Arch Neurol",
            title="t", year=2002, first_page="1",
            authors_last_names=["Someone"])
        assert len(mod.find_mismatches(ref, None, eu)) >= 1
