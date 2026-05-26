# v1.7.9 — CRITICAL: read the WORKFLOW section first

## The deep-to-deep audit on your v1.7.8 zip

### What I confirmed by unzipping it

1. **v1.7.8 is real bugfix work** — the CHANGELOG describes a serious silent-skip fix
   in MIRIAD tests. Your 237→239 test count growth is genuine.

2. **All v1.7.7 patches are gone again.** I grep'd the v1.7.8 zip:
   - `n = 16` is back in `test_scanner_factorial.py:62` (I removed it in v1.7.2 and v1.7.7)
   - `_has_journal_claim` count in resolver: 0 (added in v1.7.5 and v1.7.7)
   - `strict=True` count in sample_size: 0 (added in v1.7.2 and v1.7.7)
   - Unused datetime imports back in `adapter_miriad.py:118`
   - `**.pre-commit-config.yaml` is MISSING from the zip** — even though
     your terminal showed you committed it successfully

3. **CI failure is identical to v1.7.6 and earlier** — same 20 ruff errors,
   same files, same line numbers. Resolver back to v1.7.0 logic.

### Diagnosis

You ARE pushing successfully — the v1.7.7 commit landed (commit hash 8849a3f
appeared in your terminal). But then you did v1.7.8 work that **regenerated
files from a different source** that didn't include the v1.7.7 changes.

The `.pre-commit-config.yaml` missing from this zip is the key clue. It WAS
committed (your terminal showed commit 26d78a7). But it's not in the zip
you're sending me. Two possibilities:

1. The zip is being created by exporting a "release snapshot" from a
   different folder, not by zipping your actual working repo
2. The folder you're zipping is a v1.7.8 work-in-progress folder that you
   built fresh, separate from the one where pre-commit was installed

Either way: **the pre-commit hook is not running on the machine producing
the v1.7.8 push.** That's why the regressions keep coming back.

## What this patch fixes

| Category | Files | Fix |
|---|---|---|
| Pre-commit config | `.pre-commit-config.yaml` | Recreated with `--unsafe-fixes` to catch UP038 next time |
| Resolver | `scripts/verify_citations.py` | v1.7.5 warning-only mode + all regex bugfixes |
| Lint (ruff --fix) | 17 source/test files | All 27 ruff errors auto-fixed (incl. 6 UP038 from last session) |

Local CI replay shows:
```
ruff: All checks passed!
pytest: 239 passed, 2 skipped
resolver --offline: All structural checks passed
```

## CRITICAL: how to push WITHOUT it being overwritten this time

### Path A — Push directly from this patch zip (recommended)

```powershell
# Find your ACTUAL git repo folder (the one with .git/ inside it)
# This is the folder where `git push` last succeeded.
cd C:\Users\Dell\Downloads\NeuroTCS_extracted\NeuroTCS

# Extract the patch over THAT folder
Expand-Archive -Path "$HOME\Downloads\neurotcs_v1.7.9_FINAL_patch.zip" -DestinationPath . -Force

# Verify locally
python -m pytest tests/ -q
ruff check src/ tests/ scripts/

# Commit
git add -A
git commit -m "v1.7.9: re-apply v1.7.5 resolver + ruff --fix --unsafe-fixes + pre-commit config"
git push origin main
```

### Path B — If you have a separate "release" folder, STOP zipping that

If you've been zipping a separate folder (e.g.,
`NeuroTCS_v1.7.8/` vs `NeuroTCS/`), your workflow is:

```
[ work folder ]  →  [ creates v1.7.8 ]  →  [ uploads to me ]
[ git folder  ]  ←  [ "git push" ]      ←  [ patches I send ]
```

These are two different folders. The patches you push don't end up in the
work folder. That's why v1.7.8 looks like it has none of the patches.

**Fix**: pick ONE folder. The one with `.git/` inside it. Do BOTH the
v1.7.x feature work AND the git push from that single folder.

Run this in PowerShell to confirm which folder has the git connection:

```powershell
cd C:\Users\Dell\Downloads\NeuroTCS_extracted\NeuroTCS
ls .git
# If you see hooks/, objects/, refs/, etc — this is the git folder.
# If "Cannot find path" — this is NOT the git folder.

git remote -v
# Should show: origin  https://github.com/DrMaruf1991/NeuroTCS.git
```

Then use ONLY that folder for everything going forward.

## How to test pre-commit is actually running before you push

After applying the patch and BEFORE pushing, run:

```powershell
pre-commit run --all-files
```

You should see `ruff Passed`. If pre-commit isn't installed in this folder,
run `pre-commit install` again.

## File inventory

```
NeuroTCS/
├── .pre-commit-config.yaml                                ← was missing from v1.7.8
├── PUSH_TO_GITHUB.md
├── scripts/
│   ├── run_aim3_miriad.py
│   └── verify_citations.py                                ← v1.7.5 logic restored
├── src/neurotcs/
│   ├── __init__.py
│   ├── audit_core/trajectory.py                           ← UP038 fix
│   ├── fairness/__init__.py
│   ├── input_contract/v1_1/
│   │   ├── adapters/adapter_miriad.py                     ← UP038 + unused imports
│   │   └── validate.py                                    ← UP038 × 3
│   ├── sample_size/__init__.py                            ← zip strict=True
│   └── scanner_factorial/__init__.py
└── tests/
    ├── audit_core/
    │   ├── test_audit_core.py
    │   └── test_real_miriad_audit.py
    ├── fairness/test_fairness.py
    ├── input_contract/test_miriad_adapter.py
    ├── sample_size/test_sample_size.py
    ├── scanner_factorial/test_scanner_factorial.py        ← drop unused n=16
    ├── scripts/test_run_aim3_miriad.py
    ├── silent_deployment/test_silent_deployment.py
    └── threshold_derivation/test_threshold_derivation.py
```

19 fixed files + PUSH_TO_GITHUB.md. Everything verified locally end-to-end.
