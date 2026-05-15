#!/usr/bin/env bash
set -euo pipefail

UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}" uv run --project backend python -m unittest discover -s backend/tests -t backend -v
