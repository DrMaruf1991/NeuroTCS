"""v1.52.0 -- provenance registry: regression-lock the primary-source
verification of every external citation and verbatim quote.

These tests make the citation verification REPRODUCIBLE and tamper-evident:
- every DOI/PMID constant scattered across the codebase must match the
  verified registry (neurotcs.provenance.REGISTRY);
- every verbatim quote the registry marks as verified must actually appear in
  the source file that relies on it.

If anyone edits an identifier or a verbatim quote without re-verifying and
updating the registry, one of these fails -- the drift cannot pass silently.
"""
from __future__ import annotations

import pathlib

from neurotcs.provenance import REGISTRY, VERIFICATION_DATE

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "neurotcs"


def _norm_quote(s: str) -> str:
    # normalize whitespace AND dash variants (ASCII hyphen vs Unicode minus/
    # en-dash), since the codebase is strict-ASCII while sources may use U+2212.
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    return " ".join(s.split())


def test_verification_date_present():
    assert VERIFICATION_DATE and len(VERIFICATION_DATE) == 10


def test_registry_identifiers_wellformed():
    for key, c in REGISTRY.items():
        assert c.key == key
        assert c.doi.startswith("10."), f"{key}: DOI not a DOI"
        # PMID is optional (some journals are DOI-only); when present it must be
        # a well-formed 7-8 digit identifier.
        if c.pmid:
            assert c.pmid.isdigit() and 7 <= len(c.pmid) <= 8, f"{key}: bad PMID"
        assert c.source, f"{key}: missing verification source"


def test_module_constants_match_registry():
    """DOI/PMID constants defined in the codebase must equal the registry."""
    pairs = {
        "kwong_2022": SRC / "silent_deployment" / "__init__.py",
        "decide_ai_2022": SRC / "silent_deployment" / "__init__.py",
        "larson_2025": SRC / "threshold_derivation" / "__init__.py",
        "future_ai_2024": SRC / "fairness" / "__init__.py",
        "riley_2024": SRC / "sample_size" / "__init__.py",
    }
    for key, path in pairs.items():
        text = path.read_text()
        c = REGISTRY[key]
        assert c.doi in text, f"{key}: registry DOI {c.doi} not in {path.name}"
        assert c.pmid in text, f"{key}: registry PMID {c.pmid} not in {path.name}"


def test_jack_2024_pmid_in_rule_packs():
    c = REGISTRY["jack_2024"]
    ad = SRC / "rulepack" / "rules" / "ad"
    blob = "\n".join(p.read_text() for p in ad.glob("*.yaml"))
    assert c.pmid in blob, "Jack 2024 PMID missing from AD rule packs"


def test_verified_quotes_present_in_sources():
    """Each verified verbatim quote must actually appear where it is relied on."""
    haystacks = {
        "jack_2024": "\n".join(
            p.read_text()
            for p in (SRC / "rulepack" / "rules" / "ad").glob("*.yaml")
        ),
        "kwong_2022": (SRC / "silent_deployment" / "__init__.py").read_text(),
        "larson_2025": (SRC / "threshold_derivation" / "__init__.py").read_text(),
    }
    for key, c in REGISTRY.items():
        if not c.quote_verified:
            continue
        hay = _norm_quote(haystacks[key])
        for q in c.verified_quotes:
            assert _norm_quote(q) in hay, (
                f"{key}: verified quote not found verbatim in source: {q[:60]}..."
            )


def test_table7_note_not_claimed_verbatim():
    """v1.54.0 diligence: the Jack 2024 Table 7 caption wording was NOT verified
    word-for-word against the primary source (only the 1A->4-6D notation and the
    diagonal progression are corroborated). The aa_2024 pack must therefore NOT
    label the Table 7 cell as a verbatim quote. This locks the correction so the
    claim cannot be silently re-upgraded to 'verbatim'."""
    aa = (SRC / "rulepack" / "rules" / "ad" / "aa_2024.yaml").read_text()
    # the specific Table 7 caption string must not appear as a verbatim claim
    assert 'Table 7 \u00a7Note (verbatim)' not in aa
    assert "diagonal shaded cells" not in aa, (
        "Table 7 caption wording reintroduced as if verbatim; it is unverified."
    )
