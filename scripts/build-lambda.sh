#!/usr/bin/env bash
# Package a single executor-tool Lambda as a zip.
# Usage: bash scripts/build-lambda.sh <tool_name>
# Output: lambdas/_dist/<tool_name>.zip

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <tool_name>" >&2
  exit 1
fi

TOOL_NAME="$1"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOL_DIR="${REPO_ROOT}/lambdas/${TOOL_NAME}"
DIST_DIR="${REPO_ROOT}/lambdas/_dist"
STAGE_DIR="$(mktemp -d)"

if [ ! -d "${TOOL_DIR}" ]; then
  echo "ERROR: ${TOOL_DIR} does not exist" >&2
  exit 1
fi

cleanup() { rm -rf "${STAGE_DIR}"; }
trap cleanup EXIT

mkdir -p "${DIST_DIR}"

echo "==> Staging Lambda source from ${TOOL_DIR}"
# Preserve the `lambdas.<tool>.*` package path so `handler.py` keeps importing
# `from lambdas.<tool>.schema import ...`. The runtime handler is configured
# as `lambdas.<tool>.handler.lambda_handler` (see infra/modules/lambdas).
PKG_DIR="${STAGE_DIR}/lambdas/${TOOL_NAME}"
mkdir -p "${PKG_DIR}"
# No `lambdas/__init__.py` — namespace package so the layer's `lambdas.shared`
# remains visible alongside this function's `lambdas.<tool>`.
: > "${PKG_DIR}/__init__.py"
find "${TOOL_DIR}" -maxdepth 1 -name '*.py' -exec cp {} "${PKG_DIR}/" \;
if [ -f "${TOOL_DIR}/requirements.txt" ]; then
  echo "==> Installing tool-local dependencies"
  python3 -m pip install \
    --platform manylinux2014_aarch64 \
    --target "${STAGE_DIR}" \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    -r "${TOOL_DIR}/requirements.txt"
fi

OUT_ZIP="${DIST_DIR}/${TOOL_NAME}.zip"
rm -f "${OUT_ZIP}"
echo "==> Zipping → ${OUT_ZIP}"
(cd "${STAGE_DIR}" && python3 -m zipfile -c "${OUT_ZIP}" *)

echo "==> Done: $(du -h "${OUT_ZIP}" | cut -f1)"
