#!/bin/bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
rea_node="${REA_NODE:-/opt/homebrew/opt/node@26/bin/node}"
if [[ ! -x "$rea_node" ]]; then rea_node="$(command -v node)"; fi
export PATH="$(dirname "$rea_node"):$PATH"
exec "$rea_node" "$project_dir/.tools/rea/node_modules/rea-agents/scripts/rea.mjs" "$@"
