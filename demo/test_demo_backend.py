"""Regression suite for the demo backend behaviours that are NOT data-gated.

These lock in the invariants proven during verification so the same classes of
bug cannot recur:

  * availability = configured AND present (a set-but-missing path is NOT available),
    and the /api/cohorts `available` field never disagrees with config.data_available;
  * uploads reuse the engine and de-identify (subject ids hashed everywhere,
    including the bundle), with a deterministic-yet-input-sensitive audit_id;
  * label normalization is opt-in and reported; fail-closed error paths;
  * /api/audit/upload is not captured by the /api/audit/{cohort} route.

Run:  pytest demo/test_demo_backend.py -v
(Unlike test_web_parity.py these need no DUA data -- they build tiny inputs.)
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pandas as pd
import pytest
from starlette.testclient import TestClient

from demo.app import app
from demo.config import COHORTS, COHORTS_BY_ID, data_available


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _staging_csv(reversals: bool = False) -> bytes:
    rows = []
    for s in range(1, 8):
        seq = ["AD", "MCI", "CN"] if (reversals and s % 2) else ["CN", "MCI", "AD"]
        for v, st in enumerate(seq):
            rows.append({"subject_id": f"REAL_{s}", "visit_date": f"20{10 + v:02d}-01-01",
                         "state": st})
    return pd.DataFrame(rows).to_csv(index=False).encode()


# --------------------------------------------------------------------------- #
# Availability: configured AND present (root-cause guard)
# --------------------------------------------------------------------------- #
def test_data_available_requires_existence(monkeypatch, tmp_path):
    spec = COHORTS_BY_ID["a4"]
    var = spec.env_vars[0]

    monkeypatch.delenv(var, raising=False)
    assert data_available(spec) is False, "unset path must be unavailable"

    monkeypatch.setenv(var, str(tmp_path / "does_not_exist.csv"))
    assert data_available(spec) is False, "set-but-missing path must be unavailable"

    real = tmp_path / "cdr.csv"
    real.write_text("x")
    monkeypatch.setenv(var, str(real))
    assert data_available(spec) is True, "existing path must be available"


def test_directory_path_is_available(monkeypatch, tmp_path):
    """MIRIAD points at a directory -- Path.exists() must accept it."""
    spec = COHORTS_BY_ID["miriad"]
    d = tmp_path / "miriad"
    d.mkdir()
    monkeypatch.setenv(spec.env_vars[0], str(d))
    assert data_available(spec) is True


def test_cohorts_available_never_disagrees_with_predicate(client, monkeypatch, tmp_path):
    """The /api/cohorts `available` field must equal config.data_available for
    every cohort -- including a configured-but-missing path (the root defect)."""
    monkeypatch.setenv(COHORTS_BY_ID["a4"].env_vars[0], str(tmp_path / "missing.csv"))
    body = client.get("/api/cohorts").json()
    by_id = {c["cohort_id"]: c for c in body["cohorts"]}
    for spec in COHORTS:
        assert by_id[spec.cohort_id]["available"] is data_available(spec), (
            f"{spec.cohort_id}: /api/cohorts available disagrees with data_available"
        )
    # and the specific root case: missing path -> available False
    assert by_id["a4"]["available"] is False


def test_cohorts_never_leak_the_data_path(client, monkeypatch):
    """The resolved data path must never appear in /api/cohorts."""
    monkeypatch.setenv(COHORTS_BY_ID["a4"].env_vars[0], "/secret/mount/DUA/cdr.csv")
    assert "/secret/mount/DUA" not in json.dumps(client.get("/api/cohorts").json())


# --------------------------------------------------------------------------- #
# Upload: reuse + de-identification
# --------------------------------------------------------------------------- #
def _describe(client, name, data, mime="text/csv"):
    return client.post("/api/upload/describe", files={"file": (name, data, mime)}).json()


def _audit(client, name, data, mapping, mime="text/csv", normalize=None):
    form = {"mapping": json.dumps(mapping)}
    if normalize is not None:
        form["normalize"] = normalize
    return client.post("/api/audit/upload", files={"file": (name, data, mime)}, data=form)


def test_upload_reuses_engine_and_returns_ctcs(client):
    data = _staging_csv(reversals=True)
    d = _describe(client, "t.csv", data)
    assert d["suggested"]["subject_id"] == "subject_id"
    r = _audit(client, "t.csv", data, d["suggested"]).json()
    assert r["ctcs"] is not None and r["n_transitions"] > 0
    assert r["rulepack_id"].startswith("ad/niaaa_2018")
    assert r["citation_pmid"] == "29653606"


def test_upload_hashes_ids_everywhere(client):
    """No raw id may appear in flags OR the bundle; flag ids are 12-hex hashes."""
    data = _staging_csv(reversals=True)
    d = _describe(client, "t.csv", data)
    r = _audit(client, "t.csv", data, d["suggested"]).json()
    assert r["subject_ids_hashed"] is True
    assert "REAL_" not in json.dumps(r), "raw id leaked into the response/bundle"
    assert r["flags"], "expected reversals to flag"
    for f in r["flags"]:
        assert len(f["subject_id"]) == 12 and all(ch in "0123456789abcdef" for ch in f["subject_id"])
    # hash is exactly sha256(raw)[:12]
    assert any(f["subject_id"] == hashlib.sha256(f"REAL_{s}".encode()).hexdigest()[:12]
               for s in range(1, 8) for f in r["flags"])


def test_upload_audit_id_deterministic_and_sensitive(client):
    data = _staging_csv(reversals=True)
    d = _describe(client, "t.csv", data)
    r1 = _audit(client, "t.csv", data, d["suggested"]).json()
    r2 = _audit(client, "t.csv", data, d["suggested"]).json()
    assert r1["audit_id"] == r2["audit_id"], "same input must give same audit_id"
    # a real change (extra 3-visit subject -> new transitions) must change it
    extra = pd.read_csv(io.BytesIO(data))
    extra = pd.concat([extra, pd.DataFrame(
        [{"subject_id": "REAL_99", "visit_date": f"202{v}-01-01", "state": st}
         for v, st in enumerate(["CN", "MCI", "AD"])])])
    data2 = extra.to_csv(index=False).encode()
    r3 = _audit(client, "t.csv", data2, _describe(client, "t.csv", data2)["suggested"]).json()
    assert r3["audit_id"] != r1["audit_id"] and r3["n_transitions"] > r1["n_transitions"]


def test_upload_hashing_preserves_ctcs(client):
    """cTCS/counts over hashed ids equal those over raw ids (hashing is a bijection)."""
    from neurotcs.io import tables_to_submission
    from neurotcs.io.readers import _read_bytes_as_table
    from neurotcs.orchestration.orchestrator import run_full_audit
    data = _staging_csv(reversals=True)
    t = _read_bytes_as_table(data, "t.csv", allow_pdf=False, encoding=None, decisions=[])
    sub = tables_to_submission(t, {"clinical": {"sheet": "t", "subject_id": "subject_id",
                                                "state": "state", "visit_date": "visit_date"},
                                   "ranges": []}, warnings=[])
    raw = next(lyr for lyr in run_full_audit(sub, expected_layers=["staging_clinical"]).layers
               if lyr.layer == "staging_clinical" and lyr.ran).summary
    r = _audit(client, "t.csv", data, _describe(client, "t.csv", data)["suggested"]).json()
    assert abs(raw["ctcs"] - r["ctcs"]) < 1e-12
    assert raw["n_transitions"] == r["n_transitions"]
    assert raw["n_flagged"] == r["n_flagged"]


# --------------------------------------------------------------------------- #
# Label normalization: opt-in, reported, no-op on canonical labels
# --------------------------------------------------------------------------- #
def _textlabel_csv() -> bytes:
    rows = [{"subject_id": f"S{s}", "visit_date": f"20{10 + v:02d}-01-01", "DX": st}
            for s in range(1, 6) for v, st in enumerate(["Normal", "MCI", "Alzheimer's disease"])]
    return pd.DataFrame(rows).to_csv(index=False).encode()


def test_normalize_on_maps_text_labels(client):
    data = _textlabel_csv()
    m = _describe(client, "t.csv", data)["suggested"]
    m["state"] = "DX"
    r = _audit(client, "t.csv", data, m, normalize="true").json()
    assert r["ctcs"] is not None
    pairs = {(x["raw"], x["canonical"]) for x in r["label_normalization"]}
    assert {("Normal", "CN"), ("Alzheimer's disease", "AD")} <= pairs


def test_normalize_off_fails_closed_on_text_labels(client):
    data = _textlabel_csv()
    m = _describe(client, "t.csv", data)["suggested"]
    m["state"] = "DX"
    resp = _audit(client, "t.csv", data, m, normalize="false")
    assert resp.status_code == 422


def test_normalize_is_noop_on_canonical_labels(client):
    data = _staging_csv()
    d = _describe(client, "t.csv", data)
    on = _audit(client, "t.csv", data, d["suggested"], normalize="true").json()
    off = _audit(client, "t.csv", data, d["suggested"], normalize="false").json()
    assert on["audit_id"] == off["audit_id"]
    assert on["label_normalization"] == []


def _raw_staging_summary(data: bytes):
    """Audit `data` through the bare engine (CLI-equivalent, no upload transforms)."""
    from neurotcs.io import tables_to_submission
    from neurotcs.io.readers import _read_bytes_as_table
    from neurotcs.orchestration.orchestrator import run_full_audit
    t = _read_bytes_as_table(data, "t.csv", allow_pdf=False, encoding=None, decisions=[])
    sub = tables_to_submission(t, {"clinical": {"sheet": "t", "subject_id": "subject_id",
                                                "state": "state", "visit_date": "visit_date"},
                                   "ranges": []}, warnings=[])
    return next((lyr for lyr in run_full_audit(sub, expected_layers=["staging_clinical"]).layers
                 if lyr.layer == "staging_clinical" and lyr.ran), None)


def test_normalize_does_not_corrupt_missing_states(client):
    """Regression: normalization must NOT stringify a missing state (NaN) into the
    literal 'nan'. Doing so would keep the visit and add spurious impossible
    transitions, diverging from the CLI. A missing state must stay missing so the
    engine drops that visit -- normalize ON must equal the raw engine."""
    import numpy as np
    rows = [{"subject_id": "S1", "visit_date": "2010-01-01", "state": "CN"},
            {"subject_id": "S1", "visit_date": "2011-01-01", "state": np.nan},  # missing
            {"subject_id": "S1", "visit_date": "2012-01-01", "state": "AD"},
            {"subject_id": "S2", "visit_date": "2010-01-01", "state": "CN"},
            {"subject_id": "S2", "visit_date": "2011-01-01", "state": "MCI"},
            {"subject_id": "S2", "visit_date": "2012-01-01", "state": "AD"}]
    data = pd.DataFrame(rows).to_csv(index=False).encode()
    raw = _raw_staging_summary(data).summary
    mp = {"sheet": "t", "subject_id": "subject_id", "state": "state", "visit_date": "visit_date"}
    on = _audit(client, "t.csv", data, mp, normalize="true").json()
    assert on["n_transitions"] == raw["n_transitions"], "normalize changed transition count on NaN"
    assert on["n_flagged"] == raw["n_flagged"], "normalize added spurious flags on NaN"
    assert abs(on["ctcs"] - raw["ctcs"]) < 1e-12, "normalize changed cTCS on NaN"


def test_numeric_state_column_is_detected_and_flagged(client):
    """A numeric-looking state column must be surfaced so the UI can warn: describe
    lists it under numeric_like, and audit sets state_looks_numeric. A text state
    column must NOT be flagged."""
    rows = [{"subject_id": f"S{s}", "visit_date": f"20{10 + v:02d}-01-01",
             "clinical_stage": st, "dx_code": c}
            for s in range(1, 6) for v, (st, c) in enumerate([("CN", 1), ("MCI", 2), ("AD", 3)])]
    data = pd.DataFrame(rows).to_csv(index=False).encode()
    d = _describe(client, "t.csv", data)
    sheet = next(iter(d["sheets"]))
    assert "dx_code" in d["sheets"][sheet]["numeric_like"]
    assert "clinical_stage" not in d["sheets"][sheet]["numeric_like"]

    mp = {"sheet": sheet, "subject_id": "subject_id", "visit_date": "visit_date"}
    num = _audit(client, "t.csv", data, {**mp, "state": "dx_code"}).json()
    txt = _audit(client, "t.csv", data, {**mp, "state": "clinical_stage"}).json()
    assert num["state_looks_numeric"] is True
    assert txt["state_looks_numeric"] is False


def test_adni_fine_grained_stages_are_recognized(client):
    """ADNI sub-stages (SMC/EMCI/LMCI) are read and audited, not rejected -- a real
    CN->EMCI->LMCI->AD progression must produce a score, not a refusal."""
    rows = [{"subject_id": f"S{s}", "visit_date": f"20{10 + v:02d}-01-01", "state": st}
            for s in range(1, 5) for v, st in enumerate(["CN", "EMCI", "LMCI", "AD"])]
    data = pd.DataFrame(rows).to_csv(index=False).encode()
    mp = {"sheet": "t", "subject_id": "subject_id", "state": "state", "visit_date": "visit_date"}
    r = _audit(client, "t.csv", data, mp, normalize="true").json()
    assert r["ctcs"] is not None and r["n_transitions"] > 0


def test_adni_dementia_label_not_recognized(client):
    """Bare 'Dementia' (ADNIMERGE DX) is NOT mapped -> the audit fails closed, so a
    user is told to map Dementia->AD rather than getting a silent wrong score."""
    rows = [{"subject_id": f"S{s}", "visit_date": f"20{10 + v:02d}-01-01", "state": st}
            for s in range(1, 5) for v, st in enumerate(["CN", "MCI", "Dementia"])]
    data = pd.DataFrame(rows).to_csv(index=False).encode()
    mp = {"sheet": "t", "subject_id": "subject_id", "state": "state", "visit_date": "visit_date"}
    assert _audit(client, "t.csv", data, mp, normalize="true").status_code == 422


def test_non_null_unmappable_state_is_kept_and_flagged(client):
    """A non-null out-of-vocabulary state ('Unknown') is NOT dropped -- it is kept
    and its transitions are flagged impossible, exactly as the raw engine does."""
    rows = [{"subject_id": "S1", "visit_date": "2010-01-01", "state": "CN"},
            {"subject_id": "S1", "visit_date": "2011-01-01", "state": "Unknown"},
            {"subject_id": "S1", "visit_date": "2012-01-01", "state": "AD"},
            {"subject_id": "S2", "visit_date": "2010-01-01", "state": "CN"},
            {"subject_id": "S2", "visit_date": "2011-01-01", "state": "MCI"},
            {"subject_id": "S2", "visit_date": "2012-01-01", "state": "AD"}]
    data = pd.DataFrame(rows).to_csv(index=False).encode()
    raw = _raw_staging_summary(data).summary
    mp = {"sheet": "t", "subject_id": "subject_id", "state": "state", "visit_date": "visit_date"}
    on = _audit(client, "t.csv", data, mp, normalize="true").json()
    assert on["n_flagged"] == raw["n_flagged"] == 2  # CN->Unknown, Unknown->AD
    assert on["n_transitions"] == raw["n_transitions"]


# --------------------------------------------------------------------------- #
# Formats + fail-closed + routing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ext", ["csv", "xlsx", "parquet", "json", "jsonl"])
def test_tabular_formats_read_in_memory(client, ext, tmp_path):
    df = pd.DataFrame([{"subject_id": f"S{s}", "visit_date": f"20{10 + v:02d}-01-01",
                        "state": x} for s in range(1, 6) for v, x in enumerate(["CN", "MCI", "AD"])])
    p = tmp_path / f"f.{ext}"
    {"csv": lambda: df.to_csv(p, index=False),
     "xlsx": lambda: df.to_excel(p, index=False),
     "parquet": lambda: df.to_parquet(p),
     "json": lambda: df.to_json(p, orient="records"),
     "jsonl": lambda: df.to_json(p, orient="records", lines=True)}[ext]()
    data = p.read_bytes()
    r = _audit(client, f"f.{ext}", data, _describe(client, f"f.{ext}", data)["suggested"],
               mime="application/octet-stream").json()
    assert r["ctcs"] is not None
    assert r["read_mode"] == "in_memory"


def test_zip_reads_via_transient_temp_file(client, tmp_path):
    df = pd.DataFrame([{"subject_id": f"S{s}", "visit_date": f"20{10 + v:02d}-01-01",
                        "state": x} for s in range(1, 6) for v, x in enumerate(["CN", "MCI", "AD"])])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("staging.csv", df.to_csv(index=False))
    data = buf.getvalue()
    r = _audit(client, "f.zip", data, _describe(client, "f.zip", data)["suggested"],
               mime="application/zip").json()
    assert r["ctcs"] is not None
    assert r["read_mode"] == "transient_temp_file"


def test_upload_fail_closed(client):
    good = _staging_csv()
    assert client.post("/api/upload/describe",
                       files={"file": ("x.pdf", b"x", "application/pdf")}).status_code == 422
    assert client.post("/api/upload/describe",
                       files={"file": ("x.csv", b"", "text/csv")}).status_code == 422
    assert _audit(client, "t.csv", good, {"sheet": "t"}).status_code == 422  # incomplete
    assert client.post("/api/audit/upload", files={"file": ("t.csv", good, "text/csv")},
                       data={"mapping": "{not json"}).status_code == 422


def test_upload_route_not_swallowed_by_cohort_route(client):
    """/api/audit/upload must hit the upload handler, not /api/audit/{cohort}."""
    data = _staging_csv()
    d = _describe(client, "t.csv", data)
    assert _audit(client, "t.csv", data, d["suggested"]).status_code == 200
    assert client.post("/api/audit/bogus").status_code == 404


def test_guide_route_served(client):
    r = client.get("/DATASET_REQUIREMENTS.md")
    assert r.status_code == 200
    assert "text/markdown" in r.headers.get("content-type", "")
    assert "subject_id" in r.text and "cTCS" in r.text


def test_rendered_guide_page_served(client):
    """The human-readable /guide page (linked from the header) renders as HTML."""
    r = client.get("/guide")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    # real rendered content, not raw markdown
    assert "Preparing your dataset" in r.text
    assert "How unmappable states are handled" in r.text
    assert "Supported formats" in r.text


def test_homepage_links_to_guide(client):
    """The main page must expose the guide so users can find it."""
    html = client.get("/").text
    assert 'href="/guide"' in html  # header link + inline help link
    assert "User guide" in html


# ---------------------------------------------------------------------------
# Self-condition contract (expert-review hardening, 2026-08): the server must
# STATE its own condition on every response and the condition must be the
# pinned one. Asserted here across representative endpoints (API, static
# page, and even 404s -- middleware wraps everything).
# ---------------------------------------------------------------------------

def test_every_response_states_engine_and_rulepack_condition(client):
    from demo.app import EXPECTED_ENGINE_VERSION, EXPECTED_RULEPACK_SHA256
    for path in ("/api/health", "/api/cohorts", "/", "/guide",
                 "/api/definitely-not-a-route"):
        resp = client.get(path)
        assert resp.headers.get("X-NeuroTCS-Engine") == (
            EXPECTED_ENGINE_VERSION
        ), f"{path}: missing/wrong X-NeuroTCS-Engine header"
        assert resp.headers.get("X-NeuroTCS-Rulepack-SHA256") == (
            EXPECTED_RULEPACK_SHA256
        ), f"{path}: missing/wrong X-NeuroTCS-Rulepack-SHA256 header"


def test_self_condition_assertion_fails_closed(client, monkeypatch):
    """If the live condition ever diverges from the pinned expectation, every
    request must become an explicit 500 naming the mismatch -- never a silent
    result under an unverified engine."""
    import demo.app as demo_app
    monkeypatch.setattr(demo_app, "_LIVE_RULEPACK_SHA256", "deadbeef")
    resp = client.get("/api/health")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "self-condition assertion failed"
    assert body["rulepack_sha256"] == "deadbeef"
