"""Rebase the reviewed patch onto the exact saved 2026-10-24 pre-write read.

No wildcard runtime regions or force option: any later byte change still fails
program_image's complete source comparison before writes are enabled.
"""
import json
from custom_image import ROOT, DEST, STOCK_SHA, prepare
from stock_update import require, digest

CANONICAL_TARGET_SHA = 'b0c1bdf013ba35a0ad86fc1104412ab788da2bd294e47c0e644f6aaec8298ad8'
CAPTURE = ROOT / 'custom-flash-20261024-102322/before.bin'
BASELINE_SHA = '5ad0acbd772c309f6db2ea8f6f0263cd6fbc03d6e72a6e2c26ff1a4eb84d8ae3'
CURRENT_TARGET_SHA = 'bec28bd21195de6d5ef50a0fb163a5dd8d669aeba2aa38e79b8ca37a2cc2073b'
SECTORS = [0x2000, 0x6000, 0x7000, 0xd000, 0x11000, 0x32000, 0x33000]

def rebase(stock, canonical, captured):
    require(len(stock) == len(canonical) == len(captured) == 0x80000, 'Incorrect image size')
    require(digest(stock) == STOCK_SHA, 'Unrecognized canonical stock image')
    require(digest(canonical) == CANONICAL_TARGET_SHA, 'Unrecognized canonical custom image')
    require(digest(captured) == BASELINE_SHA, 'Reviewed readback hash mismatch')
    changes = [i for i, (a, b) in enumerate(zip(stock, captured)) if a != b]
    require(len(changes) == 38 and min(changes) == 0x7a3bf and max(changes) == 0x7a3e7,
            'Reviewed storage difference changed')
    require(all(0x7a000 <= i < 0x7b000 for i in changes), 'Difference outside reviewed storage sector')
    actual_sectors = [a for a in range(0, len(stock), 4096) if stock[a:a+4096] != canonical[a:a+4096]]
    require(actual_sectors == SECTORS, 'Unexpected custom update sectors')
    output = bytearray(captured)
    for a in SECTORS:
        require(captured[a:a+4096] == stock[a:a+4096], 'Installed patch source sector differs')
        output[a:a+4096] = canonical[a:a+4096]
    for a in range(0, len(stock), 4096):
        if a not in SECTORS:
            require(output[a:a+4096] == captured[a:a+4096], 'Protected sector changed during rebase')
    require(digest(output) == CURRENT_TARGET_SHA, 'Rebased image differs from reviewed target')
    return bytes(output)

def prepare_current():
    stock, canonical, report = prepare()
    captured = CAPTURE.read_bytes()
    target = rebase(stock, canonical, captured)
    report = dict(report, stock_sha256=BASELINE_SHA, target_sha256=CURRENT_TARGET_SHA,
                  canonical_stock_sha256=STOCK_SHA, canonical_custom_sha256=CANONICAL_TARGET_SHA,
                  baseline_capture=str(CAPTURE.relative_to(ROOT.parent)),
                  baseline_difference={'sector':'0x7a000', 'changed_bytes':38, 'first':'0x7a3bf', 'last':'0x7a3e7'},
                  preserved='Every byte outside the same seven patch sectors is retained from the reviewed pre-write readback')
    (DEST/'custom-device-layout-current.bin').write_bytes(target)
    (DEST/'current-manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    (ROOT.parent/'docs/evidence/custom-baseline.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Reviewed current baseline: {BASELINE_SHA}')
    print(f'Custom target preserving current storage: {CURRENT_TARGET_SHA}')
    return captured, target, report

if __name__ == '__main__': prepare_current()
