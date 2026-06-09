# Releasing NeuroTCS

This is the repeatable, world-class release procedure. NeuroTCS is a private
repository distributed as versioned wheels attached to GitHub Releases (no
public PyPI). Following these steps produces a citable, reproducible artifact.

## 0. Pre-flight (must pass before tagging)

```bash
ruff check src/ tests/ scripts/         # must be clean
python -m pytest -q                     # full suite must pass
```

The version-consistency guard (`tests/test_version_consistency.py`) enforces
that `pyproject.toml`, `src/neurotcs/__init__.py`, the README version badge,
`CITATION.cff`, and `SECURITY.md` all agree, and that documented counts (test
count, AD rule-pack count) match reality. If any version string drifts, the
suite fails -- fix it before releasing.

## 1. Bump the version (single source of truth)

The canonical version lives in `pyproject.toml` (`project.version`). Update it
and `src/neurotcs/__init__.py` (`__version__`) together, then update the
documented mirrors the guard checks: README version badge, README BibTeX,
`CITATION.cff` `version`, `SECURITY.md` supported-versions line. Re-run the
guard:

```bash
python -m pytest tests/test_version_consistency.py -q
```

Add a `CHANGELOG.md` entry for the release.

## 2. Build the distribution artifacts

```bash
pip install build
python -m build           # writes dist/neurotcs-<version>-py3-none-any.whl and .tar.gz
```

Verify the wheel is self-contained (ships the rule-pack and range YAMLs) and
installs clean in a fresh environment:

```bash
python -m venv /tmp/relcheck
/tmp/relcheck/bin/pip install dist/neurotcs-<version>-py3-none-any.whl
/tmp/relcheck/bin/python -c "import neurotcs; print(neurotcs.__version__)"
/tmp/relcheck/bin/neurotcs --help
```

On Windows PowerShell:

```powershell
python -m venv $env:TEMP\relcheck
& "$env:TEMP\relcheck\Scripts\pip.exe" install (Get-ChildItem dist\*.whl).FullName
& "$env:TEMP\relcheck\Scripts\python.exe" -c "import neurotcs; print(neurotcs.__version__)"
```

## 3. Tag and push

```bash
git add -A
git commit -m "vX.Y.Z (E-2026-NNN): <summary>"
git tag vX.Y.Z
git push origin HEAD
git push origin vX.Y.Z
git ls-remote --tags origin vX.Y.Z     # confirm the tag landed
```

## 4. Create the GitHub Release (the citable artifact)

Using the GitHub CLI (`gh`):

```bash
gh release create vX.Y.Z \
  dist/neurotcs-X.Y.Z-py3-none-any.whl \
  dist/neurotcs-X.Y.Z.tar.gz \
  --title "NeuroTCS vX.Y.Z" \
  --notes-file <(sed -n '/## \[X.Y.Z\]/,/## \[/p' CHANGELOG.md)
```

Or via the GitHub web UI: Releases -> Draft a new release -> choose tag
`vX.Y.Z` -> paste the CHANGELOG section as notes -> attach the wheel and sdist
from `dist/` -> Publish.

The attached wheel/sdist are what collaborators download and `pip install`.

## 5. Mint a DOI (Zenodo) for citability

NeuroTCS ships a `CITATION.cff`, which Zenodo and GitHub both read.

1. Sign in to https://zenodo.org with the GitHub account.
2. Zenodo -> Account -> GitHub -> toggle the `NeuroTCS` repository ON.
   (For a private repo, this requires authorizing Zenodo; the DOI/record
   visibility follows the repo and Zenodo settings -- review before publishing
   if the source must stay controlled.)
3. Each subsequent GitHub Release is automatically archived and assigned a
   version DOI, plus a concept DOI that always resolves to the latest version.
4. Add the resulting DOI badge to `README.md` and the DOI to `CITATION.cff`
   (`doi:` field) on the next release.

## 6. Post-release sanity

```bash
gh release view vX.Y.Z          # confirm artifacts attached
git log origin/main --oneline -1
```

## Honest note on scope

A polished release makes NeuroTCS *installable, citable, and usable as a
research instrument*. It does **not** constitute clinical or regulatory
clearance, and it does not establish that the audit flags are validated against
ground truth -- that is the study described in `VALIDATION_PROTOCOL.md`. Do not
represent a release as FDA-cleared, GxP-validated, or clinically validated. See
[`SCOPE.md`](SCOPE.md) Regulatory status.
