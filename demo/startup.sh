#!/usr/bin/env bash
# Azure App Service startup command for the NeuroTCS live demo.
#
# Set this as the App Service "Startup Command":
#     bash demo/startup.sh
#
# It installs the EXACT shipped engine from this repo (guaranteeing cTCS parity),
# installs the web deps, verifies the engine version, then serves FastAPI under
# gunicorn+uvicorn workers.
set -euo pipefail

cd "${APP_PATH:-/home/site/wwwroot}"

echo "[startup] python: $(python --version)"

# 1) Install the audit engine from THIS repo (the shipped 1.86.0), then web deps.
#    Installing from source (not a public index) is what guarantees the engine
#    matches the locked invariants.
python -m pip install --upgrade pip >/dev/null
python -m pip install . >/dev/null
python -m pip install -r demo/requirements.txt >/dev/null

# 2) Fail-closed parity guard: refuse to start if the engine version on this
#    server is not the version whose cTCS invariants the demo reproduces.
EXPECTED_VERSION="1.86.0"
ACTUAL_VERSION="$(python -c 'import neurotcs; print(neurotcs.__version__)')"
echo "[startup] neurotcs engine: ${ACTUAL_VERSION} (expected ${EXPECTED_VERSION})"
if [ "${ACTUAL_VERSION}" != "${EXPECTED_VERSION}" ]; then
  echo "[startup] FATAL: neurotcs ${ACTUAL_VERSION} != ${EXPECTED_VERSION}; the locked"
  echo "          cTCS invariants would not hold. Aborting."
  exit 1
fi

# 3) Serve. One worker keeps per-cohort locks effective and memory bounded for
#    the large NACC audit; audits run in a threadpool so the UI never blocks.
#    Raise --timeout for the largest cohort (NACC ~158k transitions).
exec gunicorn demo.app:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WEB_WORKERS:-1}" \
  --threads "${WEB_THREADS:-4}" \
  --timeout "${WEB_TIMEOUT:-600}" \
  --bind "0.0.0.0:${PORT:-8000}" \
  --access-logfile - \
  --error-logfile -
