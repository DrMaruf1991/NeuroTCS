# Bundle Authenticity

Document ID: NTCS-DOC-AUTH
Related: `src/neurotcs/orchestration/bundle.py` (INTEGRITY vs AUTHENTICITY caveat)

## What the bundle already guarantees: INTEGRITY

Every NeuroTCS audit bundle carries a `bundle_id` -- a SHA-256 content
fingerprint over the deterministic core. It guarantees:

- **Integrity / tamper-evidence.** Any edit to the deterministic core changes
  the `bundle_id`. Re-running `neurotcs verify <bundle>` recomputes the id and
  refuses if the stored and recomputed ids disagree -- so any later alteration
  is detectable.
- **Reproducibility.** Two correct implementations on any platform produce the
  same `bundle_id` from the same audit.

## What it does NOT guarantee: AUTHENTICITY

The `bundle_id` is a keyless hash. It cannot prove **who** produced a bundle: a
holder can edit the core and recompute a self-consistent `bundle_id`. Integrity
answers "is this bundle unchanged since it was produced?"; it does not answer
"who produced it?".

This is a deliberate, disclosed boundary -- not a defect. Authenticity is the
producer's to add and the verifier's to trust.

## How to add authenticity yourself (the recipe)

Because the `bundle_id` cryptographically commits to the entire deterministic
core, a detached signature **over the `bundle_id` string** authenticates the
whole audit. You do not sign the whole file -- you sign the id, and integrity
verification ties the id back to the core.

### Producer: sign the bundle_id

First confirm integrity, then read the id and sign it with your own key:

```sh
# 1. Confirm the bundle is internally consistent (integrity gate).
neurotcs verify path/to/audit.bundle.json

# 2. Extract the bundle_id.
BUNDLE_ID=$(python -c "import json,sys; \
print(json.load(open('path/to/audit.bundle.json'))['neurotcs_bundle']['bundle_id'])")

# 3. Detached-sign the id with YOUR key (produces audit.bundle.json.sig).
printf '%s' "$BUNDLE_ID" | gpg --local-user you@example.org \
    --detach-sign --armor -o audit.bundle.json.sig
```

Distribute the bundle, the `.sig`, and your public key (or its fingerprint).

### Verifier: check the signature

```sh
# 1. Integrity first -- recompute and confirm the id.
neurotcs verify path/to/audit.bundle.json

# 2. Re-extract the id the same way.
BUNDLE_ID=$(python -c "import json; \
print(json.load(open('path/to/audit.bundle.json'))['neurotcs_bundle']['bundle_id'])")

# 3. Verify the detached signature over that id, against the producer's key
#    (must already be in your keyring).
printf '%s' "$BUNDLE_ID" | gpg --verify audit.bundle.json.sig -
```

A `Good signature from ...` line means the named key signed exactly this id.

### Sigstore alternative (key-custody-free)

If you prefer not to manage long-lived keys, sign the `bundle_id` with Sigstore
`cosign` using a short-lived OIDC identity; the signature and its certificate are
logged in the public transparency log (Rekor). This trades key custody for an
identity-bound, publicly-auditable signature.

## The trust model (read this)

A signature only proves that **a particular key signed a particular id**. It does
**not** tell you whether to trust that key. Concretely:

- **NeuroTCS holds no signing key and certifies no one.** The tool provides the
  integrity anchor (`bundle_id`); it never vouches for who produced a bundle.
- **A good signature is necessary but not sufficient.** The verifier must
  separately decide whether they trust the signing key -- via a key fingerprint
  confirmed out of band, a web of trust, or (for Sigstore) the bound OIDC
  identity. That trust decision is the verifier's, not the tool's.
- **Verify integrity first, always.** Authenticate the id only after confirming
  the bundle's core matches it; otherwise a valid signature over a stale id
  could be presented alongside a tampered core. `neurotcs verify` is the
  integrity gate; the signature check is the authenticity gate; both must pass.

## Why NeuroTCS does not ship a built-in signer by default

Signing requires a key the producer holds and guards, and a key infrastructure
(GnuPG or Sigstore) on the signer's machine. For a tool whose users span clinical
and research environments -- many without GnuPG installed -- a built-in signer
would add a dependency most users would not exercise. The honest design is to
give every user the integrity anchor and the exact recipe above, so anyone who
needs authenticity can add it with standard tooling, while no one pays for
machinery they will not use. A first-party signing subcommand is a natural
addition the day a concrete need (e.g. a journal mandate for signed supplementary
bundles) justifies the dependency.
