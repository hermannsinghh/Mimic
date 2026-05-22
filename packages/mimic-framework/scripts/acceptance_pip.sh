#!/usr/bin/env bash
# Pip acceptance smoke test for mimic-framework.
# Usage:
#   ./scripts/acceptance_pip.sh              # PyPI install, layers 0-2
#   ./scripts/acceptance_pip.sh --editable   # editable install from repo root
#   MIMIC_SMOKE_LAYER=3 ./scripts/acceptance_pip.sh   # include LLM simulate (needs OPENAI_API_KEY)
set -euo pipefail

LAYER="${MIMIC_SMOKE_LAYER:-2}"
EDITABLE=false
VENV="${MIMIC_SMOKE_VENV:-/tmp/mimic-pip-test}"
TICKER="${MIMIC_SMOKE_TICKER:-WMT}"
EVENT="${MIMIC_SMOKE_EVENT:-China port closes for 30 days}"

for arg in "$@"; do
  case "$arg" in
    --editable) EDITABLE=true ;;
    -h|--help)
      echo "Usage: $0 [--editable]"
      echo "  MIMIC_SMOKE_LAYER=0|1|2|3  (default 2)"
      echo "  MIMIC_SMOKE_VENV=/path/to/venv"
      exit 0
      ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -z "${PYTHON:-}" ]]; then
  for candidate in python3.12 python3.11 python3; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      ver="$("${candidate}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
      major="${ver%%.*}"
      minor="${ver#*.}"
      if [[ "${major}" -eq 3 && "${minor}" -ge 11 ]]; then
        PYTHON="${candidate}"
        break
      fi
    fi
  done
  PYTHON="${PYTHON:-python3}"
fi

echo "==> Mimic pip smoke test (target layer: ${LAYER})"
echo "    venv: ${VENV}"
echo "    editable: ${EDITABLE}"

# --- Layer 0: venv + install + entry point ---
if [[ ! -d "${VENV}" ]]; then
  echo "==> [L0] Creating venv at ${VENV}"
  "${PYTHON}" -m venv "${VENV}"
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"

pip install --upgrade pip -q

if [[ "${EDITABLE}" == true ]]; then
  echo "==> [L0] pip install -e ${ROOT}[dev,dotenv]"
  pip install -e "${ROOT}[dev,dotenv]" -q
else
  echo "==> [L0] pip install mimic-framework[dotenv]"
  pip install "mimic-framework[dotenv]" -q
fi

pip show mimic-framework | grep -E '^(Name|Version|Location):'

mimic --help >/dev/null
SMOKE_CWD="${TMPDIR:-/tmp}/mimic-smoke-run"
mkdir -p "${SMOKE_CWD}"
(
  cd "${SMOKE_CWD}"
  python -c "import mimic; from mimic import Twin; print('[L0] import OK:', mimic.__file__)"
  if [[ "${EDITABLE}" != true ]] && python -c "import mimic, sys; import pathlib; p=pathlib.Path(mimic.__file__).resolve(); sys.exit(0 if 'site-packages' in str(p) else 1)"; then
    echo "[L0] import path is site-packages (PyPI install verified)"
  elif [[ "${EDITABLE}" == true ]]; then
    echo "[L0] editable install (repo path expected)"
  fi
)
echo "[L0] PASS"

if [[ "${LAYER}" -lt 1 ]]; then
  echo "==> Done (layer ${LAYER})"
  exit 0
fi

# --- Layer 1: offline formulas ---
(
  cd "${SMOKE_CWD}"
  python -c "
from mimic.formulas import cogs_sensitivity
r = cogs_sensitivity(revenue=650_000, cogs=490_000, input_shock_pct=0.15, passthrough_rate=0.40)
assert r['annual_ebitda_impact_usdM'] < 0, r
print('[L1] formulas OK, annual_ebitda_impact_usdM =', r['annual_ebitda_impact_usdM'])
"
)
echo "[L1] PASS"

if [[ "${LAYER}" -lt 2 ]]; then
  echo "==> Done (layer ${LAYER})"
  exit 0
fi

# --- Layer 2: SEC + market context (network) ---
(
  cd "${SMOKE_CWD}"
  echo "==> [L2] mimic context ${TICKER} (cwd: ${SMOKE_CWD})"
  mimic context "${TICKER}"
)
echo "[L2] PASS"

if [[ "${LAYER}" -lt 3 ]]; then
  echo "==> Done (layer ${LAYER})"
  exit 0
fi

# --- Layer 3: full simulate (LLM) ---
for envfile in "${ROOT}/deepseek.env" "${ROOT}/.env"; do
  if [[ -f "${envfile}" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "${envfile}"
    set +a
    echo "==> [L3] loaded env from ${envfile}"
    break
  fi
done
if [[ -z "${DEEPSEEK_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "[L3] SKIP: set DEEPSEEK_API_KEY in deepseek.env or OPENAI_API_KEY in .env"
  exit 1
fi
SIM_MODEL="${MIMIC_SMOKE_MODEL:-}"
if [[ -z "${SIM_MODEL}" ]]; then
  if [[ -n "${DEEPSEEK_API_KEY:-}" ]]; then
    SIM_MODEL="${DEEPSEEK_MODEL:-deepseek-chat}"
  else
    SIM_MODEL="gpt-4o"
  fi
fi

(
  cd "${SMOKE_CWD}"
  export MIMIC_ENV_FILE="${ROOT}/deepseek.env"
  [[ -f "${MIMIC_ENV_FILE}" ]] || export MIMIC_ENV_FILE="${ROOT}/.env"
  echo "==> [L3] mimic simulate ${TICKER} \"${EVENT}\" (model: ${SIM_MODEL})"
  mimic simulate "${TICKER}" "${EVENT}" -s 0.7 -m "${SIM_MODEL}"
)
echo "[L3] PASS"
echo "==> All layers 0-${LAYER} passed"
