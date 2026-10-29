#!/usr/bin/env python3
"""Register a controller from its verified read-only backup. No USB access.

Checks the backup, unpacks it with the independent upstream unpacker, requires the same
factory application, bootloader, configuration and partition map as the analysed unit,
derives this unit's stock and custom images and pins their hashes in devices.json.
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'jl-misctools/firmware'))
from stock_update import build, entry, require, digest, OEM_SHA, FACTORY_APP_SHA, BASE
from jltech.cipher import jl_sfc_cipher

REFERENCE = ROOT/'device-backup-20261022-233350'  # unit1 factory backup, fully analysed
STORAGE = ((0x7a000, 0x7f000, 'VM/BTIF/USERIF runtime storage'), (0x7f000, 0x80000, 'key/MAC'))

def verify_backup(directory):
    metadata = json.loads((directory/'metadata.json').read_text())
    require(metadata.get('passes_match') is True and metadata.get('flash_modified') is False, 'Backup did not complete')
    require((metadata['vendor'], metadata['product']) == ('BD19', 'UBOOT1.00'), 'Not a BD19 UBOOT backup')
    require(metadata['jedec_id'] == 'cd7113' and metadata['size'] == 0x80000, 'Unexpected flash device')
    first = (directory/'flash-pass1.bin').read_bytes(); second = (directory/'flash-pass2.bin').read_bytes()
    require(first == second and len(first) == 0x80000, 'Backup passes differ')
    require(digest(first) == metadata['sha256'], 'Backup hash differs from metadata')
    return first, metadata

def unpack(directory):
    out = directory/'unpacked'
    if not out.exists():
        tool = ROOT/'jl-misctools/firmware'
        log = subprocess.run([sys.executable, '-E', '-s', str(tool/'fwunpack_newfw.py'), '--dirname', str(out), str(directory/'flash-pass1.bin')],
                             capture_output=True, text=True, cwd=tool)
        (directory/'unpack.log').write_text(log.stdout + log.stderr)
        require(log.returncode == 0, 'Independent unpack failed; see unpack.log')
    return out

def compare(original, reference):
    differences = [i for i, (a, b) in enumerate(zip(original, reference)) if a != b]
    unexplained = [i for i in differences if not any(lo <= i < hi for lo, hi, _ in STORAGE)]
    regions = [{'region': name, 'start': hex(lo), 'changed_bytes': sum(lo <= i < hi for i in differences)} for lo, hi, name in STORAGE]
    return differences, unexplained, regions

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name'); parser.add_argument('backup', help='directory name under research/')
    parser.add_argument('--write', action='store_true', help='add the unit to devices.json and make it current')
    args = parser.parse_args()
    directory = ROOT/args.backup
    original, metadata = verify_backup(directory)
    reference = (REFERENCE/'flash-pass1.bin').read_bytes()
    out = unpack(directory)
    app = (out/'files/app.bin').read_bytes()
    require(digest(app) == FACTORY_APP_SHA, f'Factory application differs from the analysed version: {digest(app)}')
    for name in ('files/cfg_tool.bin', 'files/p11_code.bin', 'top/uboot.boot', 'top/isd_config.ini'):
        require((out/name).read_bytes() == (REFERENCE/'unpacked'/name).read_bytes(), name + ' differs from the analysed unit')
    plain = bytearray(original); jl_sfc_cipher(plain, BASE, 0x100, BASE, 0x190d)
    records = [entry(plain, BASE+off) for off in range(0, 0x100, 32) if plain[BASE+off+2:BASE+off+32] != b'\xff'*30]
    require(original[:BASE] == reference[:BASE], 'Bootloader or top-level partition map differs from the analysed unit')
    differences, unexplained, regions = compare(original, reference)
    if unexplained:
        raise RuntimeError(f'{len(unexplained)} byte(s) differ outside runtime storage and key/MAC, first at {unexplained[0]:#x}; review before registering')
    # Same roundtrip check as the analysed unit, then derive this unit's images.
    require(build(original, app, digest(original)) == original, 'Original-image roundtrip failed')
    oem = (ROOT/'unpacked/files/app.bin').read_bytes(); require(digest(oem) == OEM_SHA, 'OEM application missing')
    stock = build(original, oem, digest(original))
    from custom_image import patch_app
    payload = (ROOT/'q32s-analysis/vendor-payload.bin').read_bytes()
    manifest = json.loads((ROOT.parent/'docs/evidence/q32s-payload.json').read_text())
    patched, _ = patch_app(oem, payload, manifest)
    custom = build(original, patched, digest(original))
    stock_sectors = [hex(a) for a in range(0, 0x80000, 4096) if original[a:a+4096] != stock[a:a+4096]]
    custom_sectors = [hex(a) for a in range(0, 0x80000, 4096) if stock[a:a+4096] != custom[a:a+4096]]
    unit = {'description': f'Registered from {args.backup}; factory application; not yet flashed',
            'backup': args.backup, 'original_sha256': digest(original), 'stock_sha256': digest(stock), 'custom_sha256': digest(custom)}
    report = {'unit': args.name, 'metadata': metadata, 'differences_from_unit1': {'total_bytes': len(differences), 'regions': regions},
              'partition_records': len(records), 'stock_changed_sectors': stock_sectors, 'custom_changed_sectors_from_stock': custom_sectors, 'entry': unit}
    print(json.dumps(report, indent=2))
    if args.write:
        path = ROOT/'devices.json'; catalog = json.loads(path.read_text())
        require(args.name not in catalog['units'], 'Unit already registered; edit devices.json deliberately instead')
        catalog['units'][args.name] = unit; catalog['current'] = args.name
        path.write_text(json.dumps(catalog, indent=2) + '\n')
        print(f'Registered {args.name} as the current unit. Run ./scripts/check-custom.sh to rebuild and verify its images.')

if __name__ == '__main__': main()
