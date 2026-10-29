#!/bin/bash
# Thin wrapper; the setup itself is cross-platform Python. Pass --research for the analysis extras.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/setup.py "$@"
