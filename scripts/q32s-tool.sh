#!/bin/sh
# Official Linux tools in an isolated container; source tree is read-only.
set -eu
cd "$(dirname "$0")/.."
repo=$(pwd)
toolchain="$repo/.tools/jieli/jieli-linux-toolchains-20260730.1"
[ -x "$toolchain/common/bin/clang" ] || { echo 'Pinned Jieli toolchain missing' >&2; exit 1; }
mkdir -p research/q32s-analysis
exec docker run --rm --platform linux/amd64 --network none --cap-drop ALL \
  --security-opt no-new-privileges --mount "type=bind,src=$toolchain,dst=/opt/jieli,readonly" \
  --mount "type=bind,src=$repo,dst=/work,readonly" \
  --mount "type=bind,src=$repo/research/q32s-analysis,dst=/work/research/q32s-analysis" \
  -w /work -e PATH=/opt/jieli/q32s/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  debian@sha256:cba95a21c96c1f5fc2470081829363eed57706634f7dc26e8c6712934303d57a "$@"
