#!/usr/bin/env bash
# Build the shared Lambda Layer zip used by every executor tool Lambda.
# Output: lambdas/_dist/shared-layer.zip
# Target: linux/arm64 (matches AgentCore Runtime + ECS baseline).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHARED_DIR="${REPO_ROOT}/lambdas/shared"
DIST_DIR="${REPO_ROOT}/lambdas/_dist"
STAGE_DIR="$(mktemp -d)"
LAYER_PYTHON_DIR="${STAGE_DIR}/python"

cleanup() { rm -rf "${STAGE_DIR}"; }
trap cleanup EXIT

mkdir -p "${LAYER_PYTHON_DIR}" "${DIST_DIR}"

echo "==> Installing layer dependencies for linux/arm64 → ${LAYER_PYTHON_DIR}"
python3 -m pip install \
  --platform manylinux2014_aarch64 \
  --target "${LAYER_PYTHON_DIR}" \
  --implementation cp \
  --python-version 3.11 \
  --only-binary=:all: \
  --upgrade \
  -r "${SHARED_DIR}/requirements.txt"

# Preserve the `lambdas.shared.*` package path inside the layer so handlers can
# keep using `from lambdas.shared import audit_emitter, langfuse_client, ...`.
# Lambda runtime adds `<layer>/python` to sys.path; we put a real `lambdas/`
# package tree under it.
echo "==> Copying shared Python modules → ${LAYER_PYTHON_DIR}/lambdas/shared/"
mkdir -p "${LAYER_PYTHON_DIR}/lambdas/shared"
# `lambdas` is a PEP 420 namespace package: no top-level __init__.py so the
# function zip and the layer can both contribute subpackages. The subpackage
# itself (`lambdas.shared`) is a regular package with __init__.py.
: > "${LAYER_PYTHON_DIR}/lambdas/shared/__init__.py"
find "${SHARED_DIR}" -maxdepth 1 -name '*.py' -exec cp {} "${LAYER_PYTHON_DIR}/lambdas/shared/" \;

OUT_ZIP="${DIST_DIR}/shared-layer.zip"
rm -f "${OUT_ZIP}"
echo "==> Zipping → ${OUT_ZIP}"
(cd "${STAGE_DIR}" && python3 -m zipfile -c "${OUT_ZIP}" python)

echo "==> Done: $(du -h "${OUT_ZIP}" | cut -f1)"
