"""Select which controller's verified backup anchors every derived image.

Each unit has its own key/MAC sector and runtime storage, so stock and custom images
are rebuilt from that unit's original backup and pinned per unit in devices.json.
GB_DEVICE overrides the current unit, which the historical unit1 regressions use.
"""
import json, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT/'devices.json').read_text())
NAME = os.environ.get('GB_DEVICE', CATALOG['current'])
if NAME not in CATALOG['units']:
    raise RuntimeError(f'Unknown device {NAME!r}; add it to research/devices.json after a verified backup')
UNIT = CATALOG['units'][NAME]
BACKUP_DIR = ROOT/UNIT['backup']
BACKUP = BACKUP_DIR/'flash-pass1.bin'
ORIGINAL_SHA = UNIT['original_sha256']
STOCK_SHA = UNIT['stock_sha256']
CUSTOM_SHA = UNIT['custom_sha256']
STOCK_OUT = ROOT/'stock-update-prepared'/NAME
CUSTOM_OUT = ROOT/'custom-prepared'/NAME
if __name__ == '__main__':
    print(NAME)
