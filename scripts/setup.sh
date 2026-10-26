#!/bin/bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
clang -fobjc-arc -dynamiclib -framework Foundation -framework IOKit -framework IOUSBHost research/native-usb.m -o research/native-usb.dylib
sleigh_compiler="$(.venv/bin/python -c 'import pathlib,pypcode; print(pathlib.Path(pypcode.__file__).parent / "bin/sleigh")')"
"$sleigh_compiler" research/ghidra-jieli/data/languages/q32s.slaspec research/ghidra-jieli/data/languages/q32s.sla
