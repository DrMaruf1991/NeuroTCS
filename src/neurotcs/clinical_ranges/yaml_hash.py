"""
neurotcs.clinical_ranges.yaml_hash — cross-platform-stable hashing of
range-pack YAML files.

Background
----------
Through v1.10.0, the `canonical_sha256` of a range pack was computed from
`RangePack.model_dump(mode="json")` and then `json.dumps(...)`. While
deterministic within a single Python interpreter, this method exhibited
minor cross-platform variability:

  - Linux Python 3.12.3:  pack ad/aria_safety → 9fb3cbd4a5662e5e...
  - Windows Python 3.12.7: pack ad/aria_safety → 9fd140cab8d6147b... (varied)

The variability is caused by pydantic patch-version differences in how
nested model dictionaries are serialized to JSON-compatible form. The
underlying YAML file bytes are byte-identical across platforms (verified:
0 CR (0x0D) bytes in the git-stored version under LF normalization).

The fix is to hash the YAML file bytes DIRECTLY, after a deterministic
normalization step that strips any platform-introduced variation:

  1. Read the file as raw bytes
  2. Decode as UTF-8
  3. Normalize line endings to LF (\n), regardless of OS line endings
  4. Strip trailing whitespace from each line (but preserve blank lines)
  5. Ensure file ends with exactly one trailing newline
  6. Re-encode as UTF-8 bytes
  7. SHA-256 hash those bytes

This produces an IDENTICAL hash on Linux, Windows, and macOS for the same
canonical YAML content, regardless of Python patch version, line-ending
strategy, or trailing-whitespace artifacts from git checkout.

Backward compatibility
----------------------
The legacy `RangePack.canonical_sha256()` method is preserved as-is for
audit_id derivation in v1.10.x — existing flag_ids in committed audit
records remain valid. The new `yaml_sha256` is exposed as a parallel
attribute on `LoadedRangePack` and will become the primary identifier
in v1.11.0+.

Both hashes are computed at load time; if they diverge, no error is raised
(the divergence is expected for v1.10.x), but the difference can be
audited via `loaded_pack.canonical_sha256 != loaded_pack.yaml_sha256`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def normalize_yaml_bytes(raw_bytes: bytes) -> bytes:
    """Apply deterministic normalization to YAML bytes before hashing.

    Steps applied (in order):
      1. Decode as UTF-8 (any other encoding is a hard error)
      2. Normalize CRLF (\\r\\n) and CR (\\r) line endings to LF (\\n)
      3. Strip trailing whitespace from every line (preserving blank lines)
      4. Ensure exactly one trailing newline at end of file
      5. Re-encode as UTF-8 bytes

    Args:
        raw_bytes: The raw file bytes as read from disk.

    Returns:
        Normalized bytes ready for SHA-256 hashing.

    Raises:
        UnicodeDecodeError: if the file is not valid UTF-8.
    """
    text = raw_bytes.decode("utf-8")
    # Normalize line endings: CRLF -> LF, then standalone CR -> LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Strip trailing whitespace from each line, preserving blank lines
    lines = [line.rstrip() for line in text.split("\n")]
    # Re-join with LF
    text = "\n".join(lines)
    # Ensure exactly one trailing newline (strip then add one)
    text = text.rstrip("\n") + "\n"
    return text.encode("utf-8")


def yaml_sha256_of_path(yaml_path: Path) -> str:
    """Compute the canonical, cross-platform-stable SHA-256 of a YAML file.

    The hash is computed over the file's bytes after normalization via
    `normalize_yaml_bytes()`. This produces identical hashes for the same
    canonical YAML content on Linux, Windows, and macOS, regardless of
    Python patch version or git line-ending settings.

    Args:
        yaml_path: Path to the YAML file on disk.

    Returns:
        64-character hex SHA-256 digest.

    Raises:
        FileNotFoundError: if yaml_path does not exist.
        UnicodeDecodeError: if the file is not valid UTF-8.
    """
    raw_bytes = yaml_path.read_bytes()
    normalized = normalize_yaml_bytes(raw_bytes)
    return hashlib.sha256(normalized).hexdigest()


def yaml_sha256_of_bytes(raw_bytes: bytes) -> str:
    """Compute the canonical SHA-256 of raw YAML bytes after normalization.

    Convenience wrapper around `normalize_yaml_bytes()` + sha256, useful for
    testing without writing to disk.

    Args:
        raw_bytes: The raw bytes (typically as read from disk).

    Returns:
        64-character hex SHA-256 digest.
    """
    normalized = normalize_yaml_bytes(raw_bytes)
    return hashlib.sha256(normalized).hexdigest()
