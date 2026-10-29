#!/usr/bin/env python3
"""One-time setup on macOS, Windows or Linux: pinned helper repositories, a Python environment
and, on macOS, the native USB transport. `--research` adds the analysis sources and compiles
the Q32S SLEIGH description (needed for the build/audit scripts, not for flashing)."""
import os, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT/'research'
PINNED = [  # mirrors sources.lock.json
    ('jl-misctools', 'https://github.com/kagaimiq/jl-misctools.git', '0a5b12db0ef38f3042acffbe2452730a37fd2405', []),
    ('jl-uboot-tool', 'https://github.com/kagaimiq/jl-uboot-tool.git', 'adb3f18889e88ac512ce0a3c4d8cc3d3cb30696a', []),
]
RESEARCH_ONLY = [
    ('ghidra-jieli', 'https://github.com/quarkslab/ghidra-jieli.git', 'e1bd0707874b77b759401555d24839ad43af1267', []),
    ('sdk', 'https://github.com/Jieli-Tech/fw-AC63_BT_SDK.git', 'fdc018de81629e21e594d677cf05f87d288be0f0', ['apps/hid', 'cpu/bd19/tools', 'include_lib/btstack', 'include_lib/driver/cpu/bd19']),
    ('LiteEMF', 'https://github.com/LiteEMF/LiteEMF.git', '9abcfb35d50262d1652b1627efa624b00636323e', []),
]

def run(*args, **kw):
    subprocess.run(args, check=True, **kw)

def fetch(name, url, commit, sparse):
    target = RESEARCH/name
    if not (target/'.git').exists():
        print(f'Fetching {name} @ {commit[:12]}')
        run('git', 'init', '-q', str(target))
        run('git', '-C', str(target), 'remote', 'add', 'origin', url)
        if sparse: run('git', '-C', str(target), 'sparse-checkout', 'set', '--no-cone', *sparse)
        run('git', '-C', str(target), 'fetch', '-q', '--depth', '1', 'origin', commit)
        run('git', '-C', str(target), 'checkout', '-q', 'FETCH_HEAD')
    head = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    if head != commit: sys.exit(f'{name} is not at the pinned revision {commit}')

def main():
    research = '--research' in sys.argv[1:]
    os.chdir(ROOT)
    for entry in PINNED + (RESEARCH_ONLY if research else []): fetch(*entry)
    venv = ROOT/'.venv'
    python = venv/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists(): run(sys.executable, '-m', 'venv', str(venv))
    run(str(python), '-m', 'pip', 'install', '-q', '-r', str(ROOT/('requirements.txt' if research else 'requirements-flash.txt')))
    if sys.platform == 'darwin':
        if not shutil.which('clang'): sys.exit('clang is missing: install the Xcode Command Line Tools (xcode-select --install)')
        run('clang', '-fobjc-arc', '-dynamiclib', '-framework', 'Foundation', '-framework', 'IOKit', '-framework', 'IOUSBHost',
            str(RESEARCH/'native-usb.m'), '-o', str(RESEARCH/'native-usb.dylib'))
    if research:
        sleigh = subprocess.run([str(python), '-c', 'import pathlib,pypcode; print(pathlib.Path(pypcode.__file__).parent / "bin/sleigh")'],
                                capture_output=True, text=True, check=True).stdout.strip()
        run(sleigh, str(RESEARCH/'ghidra-jieli/data/languages/q32s.slaspec'), str(RESEARCH/'ghidra-jieli/data/languages/q32s.sla'))
    rel = python.relative_to(ROOT)
    prefix = '' if sys.platform == 'win32' else 'sudo '
    print(f'Setup complete. Flash with: {prefix}{rel} -u research/flash_gamebrick.py install' + (' (from an Administrator terminal)' if sys.platform == 'win32' else ''))

if __name__ == '__main__': main()
