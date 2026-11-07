#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p build
[ -x build/.venv/bin/pip ] || { python3 -m venv build/.venv && build/.venv/bin/pip install -q --upgrade pip; }
# Wheels de Linux arm64 aunque CloudShell sea x86_64; las de Python 3.14 son manylinux 2_27 y 2_28
FLAGS=(--platform manylinux_2_28_aarch64 --platform manylinux2014_aarch64 --implementation cp
       --python-version 3.14 --only-binary=:all: --no-cache-dir --quiet)
layer() {
  rm -rf "build/$1"
  mkdir -p "build/$1/python"
  build/.venv/bin/pip install "${FLAGS[@]}" --target "build/$1/python" -r "$2"
  find "build/$1" -name __pycache__ -prune -exec rm -rf {} +
}
layer model-layer backend/model_api/requirements.txt
du -sh build/model-layer backend/model_api
