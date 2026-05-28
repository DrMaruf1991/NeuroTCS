<#
.SYNOPSIS
    NeuroTCS fail-closed deploy helper. Safely mirrors a release zip into the
    working tree, runs a full pre-flight gate, and only then (optionally) does
    the git/branch/PR steps. Refuses to touch git if ANY gate fails.

.DESCRIPTION
    This script exists because three manual deploys hit the same class of bug:
    robocopy /MIR silently deleted .gitignore / .github (they are .git*-prefixed
    and excluded from the release zip), which then let bytecode caches pollute
    the commit. The fix is structural, not "remember the flags": this script
    PROTECTS every git dotfile from purge, EXCLUDES every cache at the source,
    and FAILS CLOSED -- it will not commit or push a tree that doesn't pass
    version-bump, .github-present, .gitignore-present, no-cache-staged,
    rule-pack-consistency, ruff, and pytest checks.

    Same philosophy as NeuroTCS itself: completeness/correctness enforced by the
    tool, not dependent on the operator remembering to do the right thing.

.PARAMETER Zip
    Path to the release zip (e.g. C:\Users\Dell\Downloads\NeuroTCS_v1.23.2.zip).

.PARAMETER Repo
    Path to the working git repo. Default: D:\NeuroTCS

.PARAMETER ExpectVersion
    The version string you expect this release to be (e.g. "1.23.2"). The gate
    fails if the mirrored pyproject.toml / __init__.py do not match. Optional but
    strongly recommended -- it catches "I zipped the wrong build".

.PARAMETER Commit
    If set AND all gates pass: create release/vX.Y.Z branch, add, commit, tag.
    (Local only -- still does not push.)

.PARAMETER Push
    If set AND -Commit succeeded: push the branch + tag and open a PR.
    NEVER merges -- merge stays a human decision after CI is green.

.EXAMPLE
    # Safe dry run: mirror + full gate + GO/NO-GO verdict, touches no git.
    .\deploy.ps1 -Zip C:\Users\Dell\Downloads\NeuroTCS_v1.23.2.zip -ExpectVersion 1.23.2

.EXAMPLE
    # Full path once you trust the verdict: mirror, gate, branch, commit, tag, push, PR.
    .\deploy.ps1 -Zip ...NeuroTCS_v1.23.2.zip -ExpectVersion 1.23.2 -Commit -Push
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Zip,
    [string] $Repo = "D:\NeuroTCS",
    [string] $ExpectVersion = "",
    [switch] $Commit,
    [switch] $Push
)

$ErrorActionPreference = "Stop"

# ----- protected-from-purge set (verified against repo root, 2026-05-28) -----
# Git dotfiles are excluded from the release zip, so /MIR would PURGE them from
# the working tree unless protected. This is the exact bug that bit three times.
# TRADEOFF (deliberate): because .gitignore / .pre-commit-config.yaml are in the
# exclude list, a release that intentionally CHANGES them will not have that
# change applied by the mirror -- update those two by hand on the rare occasion
# they change. Protecting them from deletion is worth that small cost.
$ProtectDirs  = @(".git", ".github", ".ruff_cache", ".pytest_cache", "__pycache__", "*.egg-info")
$ProtectFiles = @("*.pyc", ".gitignore", ".pre-commit-config.yaml")

function Write-Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Write-Bad($m)  { Write-Host "  [FAIL] $m" -ForegroundColor Red }
function Abort($m) {
    Write-Host "`nABORTED (fail-closed): $m" -ForegroundColor Red
    Write-Host "No git operations were performed. Working tree may contain the" -ForegroundColor Yellow
    Write-Host "mirrored files; 'git checkout .' + 'git clean -fd' restores it if needed." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------------------
Write-Step "Pre-flight: inputs"
if (-not (Test-Path $Zip))  { Abort "zip not found: $Zip" }
if (-not (Test-Path $Repo)) { Abort "repo not found: $Repo" }
if (-not (Test-Path (Join-Path $Repo ".git"))) { Abort "$Repo is not a git repo (no .git)" }
Write-Ok "zip:  $Zip"
Write-Ok "repo: $Repo"

# Capture pre-mirror existence of the things that keep getting deleted, so we
# can prove afterwards they survived.
$preGithub    = Test-Path (Join-Path $Repo ".github\workflows")
$preGitignore = Test-Path (Join-Path $Repo ".gitignore")

# ---------------------------------------------------------------------------
Write-Step "Extract release zip"
$tmp = Join-Path (Split-Path $Repo -Parent) "_neurotcs_deploy_extract"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $Zip -DestinationPath $tmp -Force
$src = $tmp
# zips sometimes wrap content in a single top folder; descend if so
$inner = Get-ChildItem $tmp
if ($inner.Count -eq 1 -and $inner[0].PSIsContainer -and (Test-Path (Join-Path $inner[0].FullName "pyproject.toml"))) {
    $src = $inner[0].FullName
}
if (-not (Test-Path (Join-Path $src "pyproject.toml"))) { Abort "extracted zip has no pyproject.toml at $src" }
Write-Ok "extracted to $src"

# ---------------------------------------------------------------------------
Write-Step "Safe mirror (protects git dotfiles, excludes all caches)"
# Build the robocopy argument list explicitly. PowerShell array SPLATTING into a
# native exe is unreliable; an explicit list passed with the call operator is
# not. Getting these exclusions right IS the whole point of this script, so we
# do not risk a splat eating them.
$roboArgs = @($src, $Repo, "/MIR")
$roboArgs += "/XD"; $roboArgs += $ProtectDirs
$roboArgs += "/XF"; $roboArgs += $ProtectFiles
$roboArgs += @("/NJH", "/NJS", "/NDL", "/NP")
Write-Host "  robocopy $($roboArgs -join ' ')" -ForegroundColor DarkGray
& robocopy @roboArgs | Out-Null
$rc = $LASTEXITCODE
# robocopy success = exit code 0-7; 8+ is a real failure.
if ($rc -ge 8) { Abort "robocopy failed with exit code $rc" }
Write-Ok "mirror complete (robocopy code $rc)"

# ---------------------------------------------------------------------------
Write-Step "GATE 1: protected files survived the mirror"
if ($preGithub    -and -not (Test-Path (Join-Path $Repo ".github\workflows"))) { Abort ".github/workflows was deleted by the mirror (protection failed)" }
if ($preGitignore -and -not (Test-Path (Join-Path $Repo ".gitignore")))        { Abort ".gitignore was deleted by the mirror (protection failed)" }
if (-not (Test-Path (Join-Path $Repo ".gitignore")))        { Abort ".gitignore is missing from the working tree" }
if (-not (Test-Path (Join-Path $Repo ".github\workflows"))) { Abort ".github/workflows is missing from the working tree" }
Write-Ok ".github/workflows present"
Write-Ok ".gitignore present"

Set-Location $Repo

# ---------------------------------------------------------------------------
Write-Step "GATE 2: editable install + version"
pip install -e . --quiet
if ($LASTEXITCODE -ne 0) { Abort "pip install failed" }
$ver = (python -c "import neurotcs, importlib; importlib.reload(neurotcs); print(neurotcs.__version__)").Trim()
Write-Ok "installed version: $ver"
if ($ExpectVersion -ne "" -and $ver -ne $ExpectVersion) {
    Abort "version mismatch: expected $ExpectVersion, got $ver (wrong zip, or version not bumped)"
}
# bump check vs origin/main (don't ship the same version twice)
git fetch origin main --quiet 2>$null
$mainVer = ""
$mainMatch = (git show origin/main:pyproject.toml 2>$null | Select-String '^version = "(.+)"')
if ($mainMatch) { $mainVer = $mainMatch.Matches[0].Groups[1].Value }
if ($mainVer -and $mainVer -eq $ver) {
    Abort "version $ver is already on origin/main -- bump the version before deploying"
}
if ($mainVer) { Write-Ok "version bumped: origin/main is $mainVer, this release is $ver" }
else { Write-Host "  [warn] could not read origin/main version (offline or first push) -- skipping bump check" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------
Write-Step "GATE 3: rule-pack registry consistency (no magic numbers)"
python scripts\ci\verify_rule_packs.py
if ($LASTEXITCODE -ne 0) { Abort "verify_rule_packs.py failed" }
Write-Ok "rule-pack registry consistent with filesystem"

# ---------------------------------------------------------------------------
Write-Step "GATE 4: ruff lint (blocking, matches CI)"
python -m ruff check .
if ($LASTEXITCODE -ne 0) { Abort "ruff found violations (CI would fail)" }
Write-Ok "ruff clean"

# ---------------------------------------------------------------------------
Write-Step "GATE 5: full test suite"
python -m pytest -q
if ($LASTEXITCODE -ne 0) { Abort "pytest failed (do not ship a red tree)" }
Write-Ok "pytest passed"

# ---------------------------------------------------------------------------
Write-Step "GATE 6: no caches / build artifacts staged for commit"
# .gitignore should already exclude these; this is defense-in-depth so a polluted
# tree can NEVER be committed (the exact failure from prior deploys).
$dirty = git status --porcelain | Where-Object {
    $_ -match '__pycache__' -or $_ -match '\.pyc' -or $_ -match '\.egg-info'
}
if ($dirty) {
    Write-Bad "cache/build files are not ignored:"
    $dirty | ForEach-Object { Write-Host "      $_" -ForegroundColor Red }
    Abort "bytecode/egg-info would be committed -- check .gitignore"
}
Write-Ok "no caches staged"

# ---------------------------------------------------------------------------
Write-Host "`n========================================================" -ForegroundColor Green
Write-Host " GO: all gates passed for v$ver" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green

if (-not $Commit) {
    Write-Host "`nDry run complete. No git changes made. To ship, re-run with -Commit (and -Push)." -ForegroundColor Yellow
    Write-Host "Or run manually:" -ForegroundColor Yellow
    Write-Host "  git checkout -b release/v$ver; git add -A; git commit -m `"v$ver`"; git tag v$ver" -ForegroundColor Gray
    Write-Host "  git push origin release/v$ver; git push origin v$ver; gh pr create --fill; gh pr checks --watch" -ForegroundColor Gray
    exit 0
}

# ---------------------------------------------------------------------------
Write-Step "Git: branch, add, commit, tag"
$branch = "release/v$ver"
if (git show-ref --verify --quiet "refs/heads/$branch") { Abort "branch $branch already exists -- delete it or bump version" }
git checkout -b $branch
git add -A
# final paranoia: re-confirm nothing cache-y got staged
$staged = git diff --cached --name-only | Where-Object { $_ -match '__pycache__|\.pyc|\.egg-info' }
if ($staged) { Abort "caches sneaked into the index after add -- aborting before commit" }
git commit -m "v$ver"
if ($LASTEXITCODE -ne 0) { Abort "git commit failed" }
git tag "v$ver"
Write-Ok "committed + tagged v$ver on $branch"

if (-not $Push) {
    Write-Host "`nCommitted locally on $branch (not pushed). To push + open PR, re-run with -Push," -ForegroundColor Yellow
    Write-Host "or: git push origin $branch; git push origin v$ver; gh pr create --fill" -ForegroundColor Gray
    exit 0
}

# ---------------------------------------------------------------------------
Write-Step "Git: push + open PR (does NOT merge)"
git push origin $branch
if ($LASTEXITCODE -ne 0) { Abort "git push (branch) failed" }
git push origin "v$ver"
if ($LASTEXITCODE -ne 0) { Abort "git push (tag) failed" }
gh pr create --fill
Write-Host "`nPushed $branch + tag v$ver and opened a PR." -ForegroundColor Green
Write-Host "Next (human decision): watch CI, then merge:" -ForegroundColor Yellow
Write-Host "  gh pr checks --watch" -ForegroundColor Gray
Write-Host "  gh pr merge --merge --delete-branch   # only after CI is green" -ForegroundColor Gray
Write-Host "  git checkout main; git pull origin main" -ForegroundColor Gray
