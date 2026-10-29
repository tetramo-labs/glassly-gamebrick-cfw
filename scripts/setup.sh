#!/bin/bash
# One-time setup for flashing (macOS): pinned upstream tools, a Python environment and the
# native USB transport. Pass --research to also fetch the analysis sources and compile the
# Q32S SLEIGH description (needed for the build/audit scripts, not for flashing).
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
research=0
[ "${1:-}" = "--research" ] && research=1

fetch() { # name url commit [sparse paths...]
  local name="$1" url="$2" commit="$3"; shift 3
  local dir="research/$name"
  if [ ! -d "$dir/.git" ]; then
    echo "Fetching $name @ ${commit:0:12}"
    git init -q "$dir"
    git -C "$dir" remote add origin "$url"
    if [ "$#" -gt 0 ]; then git -C "$dir" sparse-checkout set --no-cone "$@"; fi
    git -C "$dir" fetch -q --depth 1 origin "$commit"
    git -C "$dir" checkout -q FETCH_HEAD
  fi
  [ "$(git -C "$dir" rev-parse HEAD)" = "$commit" ] || { echo "$name is not at the pinned revision $commit" >&2; exit 1; }
}

# Pinned in sources.lock.json. The flasher needs the first two (JLFS cipher/CRC, BD19 RAM loader).
fetch jl-misctools https://github.com/kagaimiq/jl-misctools.git 0a5b12db0ef38f3042acffbe2452730a37fd2405
fetch jl-uboot-tool https://github.com/kagaimiq/jl-uboot-tool.git adb3f18889e88ac512ce0a3c4d8cc3d3cb30696a
if [ "$research" = 1 ]; then
  fetch ghidra-jieli https://github.com/quarkslab/ghidra-jieli.git e1bd0707874b77b759401555d24839ad43af1267
  fetch sdk https://github.com/Jieli-Tech/fw-AC63_BT_SDK.git fdc018de81629e21e594d677cf05f87d288be0f0 apps/hid cpu/bd19/tools include_lib/btstack include_lib/driver/cpu/bd19
  fetch LiteEMF https://github.com/LiteEMF/LiteEMF.git 9abcfb35d50262d1652b1627efa624b00636323e
fi

[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
command -v clang >/dev/null || { echo "clang is missing: install the Xcode Command Line Tools (xcode-select --install)" >&2; exit 1; }
clang -fobjc-arc -dynamiclib -framework Foundation -framework IOKit -framework IOUSBHost research/native-usb.m -o research/native-usb.dylib

if [ "$research" = 1 ]; then
  sleigh_compiler="$(.venv/bin/python -c 'import pathlib,pypcode; print(pathlib.Path(pypcode.__file__).parent / "bin/sleigh")')"
  "$sleigh_compiler" research/ghidra-jieli/data/languages/q32s.slaspec research/ghidra-jieli/data/languages/q32s.sla
fi
echo "Setup complete. Flash with: sudo .venv/bin/python -u research/flash_gamebrick.py install"
