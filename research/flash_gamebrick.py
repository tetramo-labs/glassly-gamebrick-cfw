#!/usr/bin/env python3
"""Flash the Glassly firmware onto a Gamebrick Mini in one go, or put the official firmware back.

    sudo .venv/bin/python -u research/flash_gamebrick.py install
    sudo .venv/bin/python -u research/flash_gamebrick.py restore

Reads the whole flash twice and saves it, derives the image from that read, writes only the
application area, and verifies the entire flash afterwards. Runtime storage and key/MAC are
never written. Needs macOS, the Jieli USB update mode (Pairing+B for two seconds after power-on
with USB connected) and the pinned IINE update archive, downloaded automatically.
"""
import argparse, ctypes, json, os, signal, sys, time
from pathlib import Path
from flash_stock import Transport, program_image, SIZE, require, digest
from gamebrick_flasher import ROOT, classify, custom_application, oem_application, oem_archive, plan

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=['install', 'restore', 'backup'])
    parser.add_argument('--oem-zip', help='rebuild the applications from this official IINE update archive instead of using the committed copies')
    args = parser.parse_args()
    output = ROOT/('gamebrick-'+args.mode+'-'+time.strftime('%Y%m%d-%H%M%S'))
    output.mkdir(); owner = ROOT.stat().st_uid
    if os.geteuid() == 0: os.chown(output, owner, -1)
    log = (output/'operation.log').open('w', buffering=1)
    class Tee:
        def __init__(self, stream): self.stream = stream
        def write(self, s): self.stream.write(s); log.write(s)
        def flush(self): self.stream.flush(); log.flush()
    sys.stdout = Tee(sys.stdout); sys.stderr = Tee(sys.stderr)
    print('Output:', output, flush=True)
    oem = custom = None
    if args.mode != 'backup':
        # Verify both applications before touching the controller.
        oem = oem_application(oem_archive(args.oem_zip)) if args.oem_zip else oem_application()
        custom = custom_application(oem if args.oem_zip else None)
        print('Official and Glassly applications verified.', flush=True)
    native = ctypes.CDLL(str(ROOT/'native-usb.dylib'))
    native.gb_error.restype = ctypes.c_char_p
    native.gb_transfer.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    signal.alarm(2100); deadline = time.monotonic() + 1800; opened = False
    try:
        print('Waiting for the controller (up to 30 minutes).', flush=True)
        print('With the controller switched ON and plugged into this Mac, hold Pairing + B for about two seconds until its light goes out, then release both.', flush=True)
        while True:
            code = native.gb_open()
            if code == 0: opened = True; break
            require(code == -2, native.gb_error().decode())
            require(time.monotonic() < deadline, 'Timed out waiting for the controller')
            time.sleep(0.25)
        device = Transport(native, []); device.initialize()
        saved = {}
        def save(name, data):
            with (output/name).open('xb') as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            saved[name] = data
        if args.mode == 'backup':
            print('Reading all flash twice.', flush=True)
            first = device.read(0, SIZE); save('flash-pass1.bin', first)
            second = device.read(0, SIZE); save('flash-pass2.bin', second)
            require(first == second, 'Backups differ; do not flash')
            report = {'sha256': digest(first), 'state': classify(first), 'passes_match': True, 'flash_modified': False}
        else:
            # program_live reads twice, keeps the live storage and refuses any other difference.
            planned = {}
            def source_and_target(current):
                planned.update(plan(current, oem, args.mode, custom))
                print(f'Controller firmware: {planned["state"]}; {len(planned["changed_sectors"])} sector(s) to write.', flush=True)
                save('stock.bin', planned['stock']); save('target.bin', planned['target'])
                return current, planned['target']
            report = program_with_plan(device, source_and_target, save)
            report.update({k: v for k, v in planned.items() if k not in ('target', 'stock')})
            report['changed_sectors'] = [hex(a) for a in report['changed_sectors']]
        report.update(mode=args.mode, hardware_functional_test='pending')
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        if args.mode == 'backup':
            print('BACKUP COMPLETE:', report['sha256'], f'({report["state"]} firmware)', flush=True)
        else:
            print('FLASH VERIFIED:', report['sha256'], flush=True)
            print('Unplug the controller, power-cycle it, then pair it in the Glassly App.' if args.mode == 'install'
                  else 'Unplug the controller and power-cycle it; it is back on the official firmware.', flush=True)
    finally:
        if opened: native.gb_close()
        for p in output.iterdir():
            if os.geteuid() == 0: os.chown(p, owner, -1)

def program_with_plan(device, source_and_target, save):
    """Read twice, plan from the first read, then hand program_live images that already carry the live storage."""
    require(not device.writes_enabled, 'Unexpected enabled writer')
    print('Reading all flash twice before allowing writes.', flush=True)
    first = device.read(0, SIZE); require(len(first) == SIZE, 'Incomplete first flash read')
    save('flash-pass1.bin', first)
    second = device.read(0, SIZE); require(second == first, 'Flash changed between preflight reads; no writes allowed')
    save('flash-pass2.bin', second)
    source, target = source_and_target(first)
    if first == target:
        print('Already running the requested firmware; nothing to write.', flush=True)
        return {'writes': 0, 'sha256': digest(first), 'full_readback_verified': True}
    device.sectors = frozenset(a for a in range(0, SIZE, 4096) if source[a:a+4096] != target[a:a+4096])
    try:
        return dict(program_image(device, source, target, 'install', before=first), matching_full_reads=2)
    finally:
        device.writes_enabled = False

if __name__ == '__main__': main()
