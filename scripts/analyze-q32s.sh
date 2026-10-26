#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
repo=$(pwd)
ghidra="$repo/.tools/ghidra/ghidra_12.2_PUBLIC"
: "${JAVA_HOME:=/opt/homebrew/opt/openjdk@25}"
export JAVA_HOME
[ -x "$ghidra/support/analyzeHeadless" ] || { echo 'Install the pinned Ghidra release; see docs/q32s.md' >&2; exit 1; }
[ -x "$ghidra/Ghidra/Features/Decompiler/os/mac_arm_64/decompile" ] || { echo 'Build the Apple Silicon decompiler; see docs/q32s.md' >&2; exit 1; }
mkdir -p research/q32s-analysis
.venv/bin/python research/prepare-q32s.py
.venv/bin/python research/extend-q32s.py
cp -R research/q32s-analysis/processor/data "$ghidra/Ghidra/Processors/JieLi/"
"$ghidra/support/sleigh" research/q32s-analysis/processor/data/languages/q32s.slaspec "$ghidra/Ghidra/Processors/JieLi/data/languages/q32s.sla"
cp "$ghidra/Ghidra/Processors/JieLi/data/languages/q32s.sla" research/q32s-analysis/processor/data/languages/q32s.sla
.venv/bin/python research/q32s-seeds.py
project="gamebrick-$(date +%Y%m%d-%H%M%S)"
"$ghidra/support/analyzeHeadless" research/q32s-analysis "$project" \
  -import research/unpacked/files/app.bin -processor q32s:LE:32:default \
  -loader BinaryLoader -loader-baseAddr 01e00120 -noanalysis \
  -scriptPath research/ghidra-scripts -postScript AnalyzeGamebrick.java \
  "$repo/research/unpacked/files/app.bin" "$repo/research/q32s-analysis/seeds.txt" \
  "$repo/research/q32s-analysis/corrected" "$repo/research/sdk/cpu/bd19/maskrom_stubs.ld" \
  > research/q32s-analysis/corrected.log 2>&1
.venv/bin/python research/test_stock_protocol.py -v
