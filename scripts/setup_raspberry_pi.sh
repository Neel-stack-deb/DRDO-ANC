#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly VENV_DIR="${PROJECT_ROOT}/.venv"
readonly DF_DIR="${PROJECT_ROOT}/external/DeepFilterNet"
readonly MODEL_ROOT="${PROJECT_ROOT}/models/dfn3_finetuned"
readonly DF_REPO="${DEEPFILTERNET_REPO:-https://github.com/Rikorose/DeepFilterNet.git}"
readonly BUILD_TMP="${PROJECT_ROOT}/.tmp"
readonly CARGO_HOME_DIR="${PROJECT_ROOT}/.cargo"

trap 'printf "\nERROR: setup failed at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

command -v python3 >/dev/null || die "python3 is required"
command -v git >/dev/null || die "git is required"

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ required; found {sys.version.split()[0]}")
PY

if [[ "$(uname -m)" != "aarch64" && "$(uname -m)" != "arm64" ]]; then
  die "64-bit ARM is required; found $(uname -m)"
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}" || die "cannot create .venv; install the OS python3-venv package"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# Keep large pip/Rust/temp files on the same volume as the checkout. This is
# important when the checkout is on a pendrive and the Pi root filesystem is small.
mkdir -p "${BUILD_TMP}" "${CARGO_HOME_DIR}"
export TMPDIR="${BUILD_TMP}"
export CARGO_HOME="${CARGO_HOME_DIR}"
export PIP_NO_CACHE_DIR=1

python -m pip install --upgrade pip setuptools wheel
python -m pip install \
  --retries 20 \
  --timeout 120 \
  -e "${PROJECT_ROOT}[gui]" \
  soundfile numpy torch \
  'maturin>=1.3,<1.5'

mkdir -p "${PROJECT_ROOT}/external"
if [[ ! -d "${DF_DIR}" ]]; then
  git clone --depth 1 "${DF_REPO}" "${DF_DIR}"
elif [[ ! -f "${DF_DIR}/pyDF/Cargo.toml" ]]; then
  die "${DF_DIR} exists but is not a DeepFilterNet source checkout"
fi

(
  cd "${DF_DIR}"
  PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 \
    maturin develop --release -m pyDF/Cargo.toml
)

[[ -f "${MODEL_ROOT}/live-finetuned/models/dfn3-epoch-130-onnx/_export_model/config.ini" ]] \
  || die "fine-tuned export config.ini is missing"
[[ -f "${MODEL_ROOT}/live-finetuned/models/dfn3-epoch-130-onnx/_export_model/checkpoints/model_130.ckpt" ]] \
  || die "fine-tuned checkpoint is missing"
for member in enc.onnx erb_dec.onnx df_dec.onnx config.ini; do
  [[ -f "${MODEL_ROOT}/live-finetuned/models/dfn3-epoch-130-onnx/onnx/${member}" ]] \
    || die "fine-tuned ONNX member is missing: ${member}"
done

native_library="${DF_DIR}/target/release/libdf.so"
[[ -f "${native_library}" ]] || die "native streaming library is missing: ${native_library}"

python - <<'PY'
import df
import numpy
import sounddevice
import soundfile
import torch
import PySide6
print("DRDO-ANC dependencies: OK")
print(f"Python: {__import__('sys').version.split()[0]}")
print(f"PyTorch: {torch.__version__}")
PY

printf '\nSetup complete. Activate with:\n  source %s/bin/activate\n' "${VENV_DIR}"
