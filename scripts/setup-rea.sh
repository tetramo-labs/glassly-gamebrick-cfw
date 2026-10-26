#!/bin/bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
rea_node="${REA_NODE:-/opt/homebrew/opt/node@26/bin/node}"
if [[ ! -x "$rea_node" ]]; then rea_node="$(command -v node)"; fi
export PATH="$(dirname "$rea_node"):$PATH"
npm install --prefix "$project_dir/.tools/rea" --no-audit --no-fund rea-agents@6.7.0
"$project_dir/scripts/rea.sh" --version
