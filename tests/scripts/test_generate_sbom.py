"""Tests for scripts/ci/generate_sbom.py -- the CycloneDX SBOM generator.

The SBOM must be (a) scoped to the locked closure (not the ambient env),
(b) valid CycloneDX 1.6, and (c) deterministic for a given lockfile.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "ci" / "generate_sbom.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_sbom", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_lock(tmp_path: Path) -> Path:
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        "# header comment\n"
        "pydantic==2.13.4\n"
        "numpy==2.4.6  # inline comment\n"
        "\n"
        "pandas==2.3.3\n",
        encoding="utf-8",
    )
    return lock


def test_sbom_parses_pins_and_is_valid_cyclonedx(tmp_path):
    mod = _load_module()
    lock = _write_lock(tmp_path)
    out = tmp_path / "sbom.json"
    rc = mod.main(["--lock", str(lock), "--out", str(out)])
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["bomFormat"] == "CycloneDX"
    assert doc["specVersion"] == "1.6"
    names = {c["name"] for c in doc["components"]}
    assert names == {"pydantic", "numpy", "pandas"}
    # every component carries a pypi purl
    assert all(c["purl"].startswith("pkg:pypi/") for c in doc["components"])
    # the top-level metadata component is neurotcs itself
    assert doc["metadata"]["component"]["name"] == "neurotcs"


def test_sbom_is_deterministic(tmp_path):
    mod = _load_module()
    lock = _write_lock(tmp_path)
    o1, o2 = tmp_path / "a.json", tmp_path / "b.json"
    mod.main(["--lock", str(lock), "--out", str(o1)])
    mod.main(["--lock", str(lock), "--out", str(o2)])
    assert o1.read_text() == o2.read_text()


def test_sbom_missing_lock_fails_closed(tmp_path):
    mod = _load_module()
    rc = mod.main(["--lock", str(tmp_path / "nope.lock"),
                   "--out", str(tmp_path / "x.json")])
    assert rc != 0
