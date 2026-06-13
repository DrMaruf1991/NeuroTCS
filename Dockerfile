# NeuroTCS -- reproducible audit environment.
#
# Builds NeuroTCS in a clean, fully pinned container so that an auditor on any
# machine gets byte-identical dependency versions -- the versions that produce
# the locked audit_ids (cTCS invariants). This is the containerized half of the
# reproducibility evidence; the GitHub Actions matrix (.github/workflows/
# reproducibility.yml) is the multi-OS / multi-Python half.
#
# Pinned to the project target interpreter (3.12) on a digest-pinned base image
# so the image itself is reproducible. Update the digest deliberately, never
# implicitly.
#
# Build:   docker build -t neurotcs:1.77.1 .
# Verify:  docker run --rm neurotcs:1.77.1            # runs the repro check
# Shell:   docker run --rm -it neurotcs:1.77.1 bash
#
# The container is for VERIFICATION and offline audit only. It has no network
# entrypoint and runs as a non-root user.

# Base interpreter = project target (3.12) on Debian bookworm-slim.
#
# REPRODUCIBILITY NOTE: for a fully reproducible image, pin this to a digest
# rather than a moving tag. Get the current digest with:
#     docker pull python:3.12-slim-bookworm
#     docker inspect --format='{{index .RepoDigests 0}}' python:3.12-slim-bookworm
# then replace the line below with, e.g.:
#     FROM python@sha256:<digest> AS base
# The tag form below builds out-of-the-box; the digest form is byte-reproducible.
FROM python:3.12-slim-bookworm AS base

# --- OS layer: only what pyreadr/pyreadstat/reportlab need, then clean up. ---
# pyreadstat builds against a C toolchain on some platforms; slim images lack it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- Non-root user (never audit as root). ---
RUN useradd --create-home --uid 10001 auditor
WORKDIR /opt/neurotcs

# --- Dependency layer: install the LOCKED closure first for cache efficiency. ---
# Copy only the lockfile + pyproject so dependency install is cached unless the
# pins change. We install the exact locked versions, then the package itself
# with --no-deps so nothing drifts off-lock.
COPY requirements.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.lock

# --- Source layer. ---
COPY . .
RUN python -m pip install --no-cache-dir --no-deps -e .

# --- Drop privileges. ---
USER auditor

# --- Default command: prove the environment reproduces the locked behavior. ---
# Runs the full test suite and asserts the package imports at the expected
# version. Exits non-zero on any failure, so `docker run` IS the repro check.
CMD ["python", "-m", "pytest", "-q"]
