"""
Cross-platform stability test for yaml_sha256.

This test pins the YAML SHA-256 hashes of every production range pack to
locked golden values. Any change to the SHAs — whether from accidental
pack-content edits, normalization regression, or library upgrades — will
trigger a hard failure.

The test also verifies that:
  1. yaml_sha256 is identical regardless of line-ending convention
     (LF on Linux/macOS, CRLF on Windows after git checkout with
      core.autocrlf=true).
  2. yaml_sha256 is identical regardless of trailing whitespace artifacts.
  3. yaml_sha256 differs from canonical_sha256 (the legacy hash) — this
     documents the v1.10.1 transition.

Introduced in v1.10.1 (2026-05-25). If this test fails after a legitimate
content change to a production pack, update the golden value AND publish a
new pack version in CHANGELOG. Do not silently overwrite golden values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.yaml_hash import (
    normalize_yaml_bytes,
    yaml_sha256_of_bytes,
    yaml_sha256_of_path,
)

# ============================================================
# LOCKED GOLDEN VALUES — DO NOT EDIT WITHOUT BUMPING PACK VERSION
# ============================================================
# These are the SHA-256 hashes of the NORMALIZED YAML bytes of each
# production range pack in v1.10.1. They are identical on Linux,
# Windows, and macOS for the same canonical YAML content.

PRODUCTION_YAML_SHA256_GOLDEN: dict[str, str] = {
    "ad/aria_safety":
        "0f5c3275c5eaaaa7e45f3636cd3a29ec7ff193d03024f624ad93ec6638af4912",
    "pet_amyloid/centiloid_consensus":
        "bfcc5f5d8ca773d9781bc99cd057f4888728b4870ae147103dfdc07f2bb92fc2",
    "genetics/apoe_consensus":
        "3d9cdca055b4b9049c9ee7636987231001c9a93d716920d630afb52016087c8f",
    "csf_biomarkers/csf_amyloid_consensus":
        "ef9b4e3c75020e618c894e52f68700fa14bd09f079ed971a25fea30d3d8c021b",
    "plasma_biomarkers/plasma_amyloid_consensus":
        "abd58cc5497cffb96abced920e9cd40823a3af059e5d313450625ab8e613e2be",
    "mri_volumetrics/structural_volumetry_consensus":
        "70710ccf013b36e5941a440a46df1b169bb505e0787a3163945e880db354191f",
    "mri_volumetrics/wmh_fazekas_consensus":
        "d4fee2be22ce6780490dc90989dde3aaef66d760a2b5b3a90f0b8753e98df0c6",
}


class TestGoldenYamlSha256:
    """Locked golden values for production-pack YAML SHAs."""

    @pytest.mark.parametrize("name,golden_sha", list(PRODUCTION_YAML_SHA256_GOLDEN.items()))
    def test_yaml_sha256_matches_golden(self, name: str, golden_sha: str) -> None:
        """The YAML SHA-256 of each production pack must match its locked
        golden value to the bit. This is the cross-platform stability
        guarantee introduced in v1.10.1.

        If this fails:
          - On a fresh clone: the SHA has drifted due to file content change.
            Verify the pack content is intentional, then update the golden
            and bump pack_version in CHANGELOG.
          - On Windows: git core.autocrlf may have introduced CRLF, but
            normalize_yaml_bytes() should strip them. If this fails on
            Windows but passes on Linux, the normalization is broken.
        """
        loaded = load_rangepack(name)
        assert loaded.yaml_sha256 == golden_sha, (
            f"YAML SHA-256 drift for {name!r}:\n"
            f"  expected: {golden_sha}\n"
            f"  actual:   {loaded.yaml_sha256}\n"
            f"If the pack content was intentionally modified, update the "
            f"golden value in this test AND bump pack_version in CHANGELOG."
        )

    def test_yaml_sha256_is_deterministic(self) -> None:
        """Repeated loads of the same pack must produce identical hashes."""
        for name in PRODUCTION_YAML_SHA256_GOLDEN:
            sha1 = load_rangepack(name).yaml_sha256
            sha2 = load_rangepack(name).yaml_sha256
            sha3 = load_rangepack(name).yaml_sha256
            assert sha1 == sha2 == sha3, (
                f"yaml_sha256 non-deterministic for {name!r}: {sha1=} {sha2=} {sha3=}"
            )

    def test_all_yaml_sha256_distinct(self) -> None:
        """No two production packs should hash to the same value."""
        all_hashes = list(PRODUCTION_YAML_SHA256_GOLDEN.values())
        assert len(all_hashes) == len(set(all_hashes)), (
            "Two production packs hash to the same value — pack-collision bug"
        )


class TestLineEndingNormalization:
    """Verify that normalize_yaml_bytes() produces identical hashes
    regardless of platform line-ending convention."""

    def test_lf_and_crlf_produce_same_hash(self) -> None:
        """A YAML file with LF line endings and the same file with CRLF
        line endings must produce identical SHA-256 hashes after
        normalization. This is the Windows reproducibility guarantee."""
        content_lf = b"foo: 1\nbar: 2\nbaz: 3\n"
        content_crlf = b"foo: 1\r\nbar: 2\r\nbaz: 3\r\n"
        content_cr = b"foo: 1\rbar: 2\rbaz: 3\r"

        sha_lf = yaml_sha256_of_bytes(content_lf)
        sha_crlf = yaml_sha256_of_bytes(content_crlf)
        sha_cr = yaml_sha256_of_bytes(content_cr)

        assert sha_lf == sha_crlf, (
            f"LF vs CRLF mismatch: {sha_lf=} vs {sha_crlf=}"
        )
        assert sha_lf == sha_cr, (
            f"LF vs CR mismatch: {sha_lf=} vs {sha_cr=}"
        )

    def test_trailing_whitespace_normalized(self) -> None:
        """Trailing whitespace on lines must not affect the hash."""
        clean = b"foo: 1\nbar: 2\n"
        with_trailing = b"foo: 1   \nbar: 2\t\n"
        assert yaml_sha256_of_bytes(clean) == yaml_sha256_of_bytes(with_trailing)

    def test_trailing_newline_count_normalized(self) -> None:
        """Zero, one, two, or many trailing newlines must not affect hash."""
        zero = b"foo: 1\nbar: 2"
        one = b"foo: 1\nbar: 2\n"
        two = b"foo: 1\nbar: 2\n\n"
        many = b"foo: 1\nbar: 2\n\n\n\n"

        h_zero = yaml_sha256_of_bytes(zero)
        h_one = yaml_sha256_of_bytes(one)
        h_two = yaml_sha256_of_bytes(two)
        h_many = yaml_sha256_of_bytes(many)

        assert h_zero == h_one == h_two == h_many, (
            f"Trailing newline count affects hash: "
            f"{h_zero=} {h_one=} {h_two=} {h_many=}"
        )

    def test_content_change_changes_hash(self) -> None:
        """A genuine content change must alter the hash. This is a
        sanity check that normalization doesn't over-normalize."""
        a = b"foo: 1\nbar: 2\n"
        b = b"foo: 1\nbar: 3\n"  # value changed
        assert yaml_sha256_of_bytes(a) != yaml_sha256_of_bytes(b)

    def test_unicode_content_preserved(self) -> None:
        """UTF-8 content (e.g., greek letters in citations) must be
        preserved through normalization."""
        content = "alpha: α\nbeta: β\n".encode()
        normalized = normalize_yaml_bytes(content)
        assert "α".encode() in normalized
        assert "β".encode() in normalized

    def test_non_utf8_raises(self) -> None:
        """Non-UTF-8 bytes must raise UnicodeDecodeError, not silently
        produce a corrupt hash."""
        bad_bytes = b"\xff\xfe\x80\x81"
        with pytest.raises(UnicodeDecodeError):
            normalize_yaml_bytes(bad_bytes)


class TestBackwardCompatibility:
    """Verify that the legacy canonical_sha256 is still exposed alongside
    the new yaml_sha256, so v1.10.x audit_ids remain reproducible."""

    @pytest.mark.parametrize("name", list(PRODUCTION_YAML_SHA256_GOLDEN.keys()))
    def test_both_hashes_present(self, name: str) -> None:
        loaded = load_rangepack(name)
        # canonical_sha256 (legacy) is still computed
        assert isinstance(loaded.canonical_sha256, str)
        assert len(loaded.canonical_sha256) == 64
        # yaml_sha256 (new) is also computed
        assert isinstance(loaded.yaml_sha256, str)
        assert len(loaded.yaml_sha256) == 64

    def test_canonical_and_yaml_hashes_differ(self) -> None:
        """The two hashes use different methods and should generally differ.
        If they ever match, it's coincidence."""
        loaded = load_rangepack("ad/aria_safety")
        # They COULD match by astronomical coincidence (2^-256), but in
        # practice they always differ because the underlying byte strings
        # are different (canonical-JSON vs normalized-YAML).
        assert loaded.canonical_sha256 != loaded.yaml_sha256


class TestYamlSha256OfPath:
    """Verify the convenience function yaml_sha256_of_path() agrees with
    LoadedRangePack.yaml_sha256."""

    @pytest.mark.parametrize("name", list(PRODUCTION_YAML_SHA256_GOLDEN.keys()))
    def test_path_helper_matches_loader(self, name: str) -> None:
        loaded = load_rangepack(name)
        # Resolve the YAML path
        from neurotcs.clinical_ranges import loader as _loader
        yaml_path = _loader._RANGES_ROOT / f"{name}.yaml"
        path_hash = yaml_sha256_of_path(yaml_path)
        assert path_hash == loaded.yaml_sha256, (
            f"yaml_sha256_of_path returned {path_hash!r} but loader returned "
            f"{loaded.yaml_sha256!r}"
        )

    def test_path_helper_nonexistent_raises(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist.yaml"
        with pytest.raises(FileNotFoundError):
            yaml_sha256_of_path(nonexistent)
