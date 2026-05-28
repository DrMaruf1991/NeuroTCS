# v1.20.0 Design: audit_id Scientific-Content Serialization

**Status:** DESIGN (not yet implemented)
**Author session:** 2026-05-28
**Supersedes process gap:** ERRATA E-2026-005 (root cause), to be closed by E-2026-006
**Prerequisite baseline:** v1.19.1 (clean, all available cohorts green except ADNI pending)

---

## 1. Problem statement (the contract being violated)

The audit_id contract is an if-and-only-if:

> Two runs that compute the same scientific result MUST produce the same
> audit_id; two runs that compute a different scientific result MUST produce
> a different audit_id.

This session proved the contract is currently violated in one direction:
across all six cohorts the scientific result was byte-identical (cTCS, n,
transitions, flagged all reproduced bit-exactly) yet audit_ids differed.
The audit_id is hashing fields that do not affect the scientific result.

## 2. Root cause (measured, not assumed)

`audit_id = SHA-256 over (rulepack canonical SHA, score vectors, B, seed)`
(src/neurotcs/audit_core/audit.py line 10).

The rulepack canonical SHA is produced by `_canonical_serialize` in
src/neurotcs/rulepack/loader.py (line ~64):

    def _canonical_serialize(rp: RulePack) -> bytes:
        return json.dumps(
            rp.model_dump(mode="json"),   # hashes the ENTIRE object
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")

`model_dump()` serializes ALL fields, including metadata the scoring engine
never reads. v1.12.0 (commit fbcfdfa) added the `endorsing_bodies` block and
bumped schema_version / rulepack_id / ruleset_version / effective_date. None
of those affect any audit result, yet all six cohort audit_ids drifted.

Verified by direct diff (rule_diff.py this session): every scientific field
is byte-identical between v1.11.0 (pre-drift) and current; only metadata
fields differ.

Current rulepack canonical SHA: aaac92fb901d13ea905e25d8dde5b31897cf425cb6600f6f87c72b63ed479081

## 3. Field partition (all 18 RulePack fields classified)

Field universe verified from rp.model_dump(mode="json").keys() (verify_fields.py).
Classification rule: a field is SCIENTIFIC iff the scoring engine reads it to
compute the result (field-access trace of audit_core/ this session).

SCIENTIFIC (4) -- MUST be hashed into audit_id:
  - state_space               (read scoring.py:102)
  - transition_priors         (read scoring.py:106)
  - admissible_transitions    (read via is_admissible scoring.py:167,263)
  - inadmissible_transitions  (admissibility logic)

METADATA (14) -- MUST be excluded from audit_id:
  - anchor_citation           (read only in loader.py provenance reporting)
  - clinical_source_authority (loader.py:141)
  - disease_domain            (loader.py:135)
  - effective_date            (loader.py:137)
  - endorsing_bodies          (not read by engine; added v1.12.0)
  - framework_name            (loader.py:134)
  - notes                     (descriptive)
  - override_allowed_default  (schema.py:507 only; NOT read by scoring)
  - reviewers                 (provenance)
  - rulepack_id               (audit.py:555 -- reported, not scored)
  - ruleset_version           (loader.py:136)
  - schema_version            (audit.py:557 -- reported, not scored)
  - status                    (loader.py:133,46 -- gate, not data)
  - transcribed_by            (audit.py:558 -- reported, not scored)

4 + 14 = 18. Complete, no phantom, no omission.

### 3.1 Rulings on borderline fields

- anchor_citation -> METADATA. The transitions ARE the science; a citation
  string change (e.g. DOI formatting) must not drift a scientific fingerprint.
  Citation still travels in provenance (reported fields), just not hashed.
- disease_domain / framework_name -> METADATA. Identity labels; the rules
  (not the labels) determine the computation. Still reported as provenance.
- override_allowed_default -> METADATA. Verified only in schema.py (field
  definition), never read by scoring. Note: the per-transition
  `override_allowed` (schema.py:291) is nested INSIDE transition objects and
  is therefore already covered when admissible/inadmissible_transitions are
  hashed.

## 4. Phantom-field lesson (recorded so it is not repeated)

The session's first rule_diff.py listed `monotone_constraints` in its
SCIENTIFIC_KEYS and reported it "IDENTICAL". This was a FALSE POSITIVE:
`monotone_constraints` is NOT a RulePack field (verify_fields.py confirms it
absent). dict.get() returned None for both versions and None == None compared
equal. Lesson: when diffing fields, assert each key EXISTS before trusting an
"identical" verdict. The corrected, verified field universe is the 18 in
section 3.

## 5. Implementation

Add an explicit scientific-field tuple and restrict the hash to it:

    _SCIENTIFIC_FIELDS = (
        "state_space",
        "admissible_transitions",
        "inadmissible_transitions",
        "transition_priors",
    )

    def _canonical_serialize(rp: RulePack) -> bytes:
        """Canonical JSON over SCIENTIFIC content only (audit_id input).
        Metadata is intentionally EXCLUDED so provenance changes never drift
        the scientific fingerprint. See ERRATA E-2026-006."""
        dump = rp.model_dump(mode="json")
        scientific = {k: dump[k] for k in _SCIENTIFIC_FIELDS if k in dump}
        return json.dumps(
            scientific, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

## 6. Two-directional proof test (the world-class artifact)

This makes the iff contract executable and permanent.

  test_audit_id_invariant_to_metadata:
    For each of the 14 metadata fields, mutate it on a loaded pack and assert
    _compute_sha256 is UNCHANGED.

  test_audit_id_sensitive_to_science:
    For each of the 4 scientific fields, mutate it and assert _compute_sha256
    CHANGES.

If both pass, the partition is proven correct in both directions.

## 7. One final re-lock of all six cohorts

The serializer change shifts every audit_id ONCE more, to the permanent
metadata-independent value. Re-lock all six cohorts in this single release,
preserving prior values per the established *_V1_x_x continuity pattern:

  - MIRIAD longitudinal (v1+v2)
  - MIRIAD test-retest (v1+v2)
  - MIRIAD fairness (v1+v2)
  - NACC (v1+v2)
  - OASIS-3 (v1+v2)
  - ADNI (v1+v2)   <- locked for the FIRST time to the permanent value;
                      do NOT ship an interim v1.19.2 ADNI lock.

Scientific invariants to assert (all measured this session; UNCHANGED by the
serializer fix because the science is unchanged):
  - MIRIAD long : cTCS=0.9854, n=69, 454 transitions, 7 flagged
  - MIRIAD retest: n=69 pairs, 0 flagged, cTCS=1.0000
  - NACC        : cTCS=0.991502 [0.990833,0.992153], n=56529, 158423 trans, 1217 flagged
  - OASIS-3     : cTCS=0.994191 [0.990264,0.996405], n_scored=1247, 7248 trans, 30 flagged
  - ADNI        : cTCS=0.994575 [0.992353,0.996079], n_scored=2958, 12006 trans, 65 flagged
  (MIRIAD CI bounds to be captured at implementation time.)

## 8. Synthetic always-on CI fixture (closes the detection gap)

The drift hid for six versions because real-data tests skip when env vars are
unset (CI never set them). Add a tiny committed synthetic cohort + locked
audit_id that runs on EVERY CI invocation, no env vars, no real data. A
metadata-only change would no longer drift it (after the serializer fix); a
scientific change WOULD, and CI catches it instantly.

## 9. ERRATA E-2026-006 (to be written at implementation)

Declare the contract (section 1), the root cause (metadata in the hash),
the structural remedy (scientific-only serialization), the proof
(two-directional test), and the stability guarantee: from v1.20.0 onward,
metadata changes (endorsing_bodies, dates, versions, citations, reviewers)
NEVER drift cohort audit_ids. Supersede the E-2026-005 re-locks with the
final metadata-independent fingerprints, preserving full continuity.

## 10. Honest scope statement

This fix makes audit_id permanently immune to METADATA drift. It does not
claim immunity to all change forever: a genuine scientific rule change SHOULD
drift the fingerprint (that is correct behavior), and engine/dependency
changes (e.g. RNG-affecting library upgrades) remain a separate concern
addressed by the synthetic CI fixture catching them loudly. The world-class
guarantee is not "never drifts" but "never drifts SILENTLY and never drifts
for non-scientific reasons."
