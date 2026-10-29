#!/usr/bin/env python3
"""Install custom firmware or restore stock, preserving current runtime storage."""
import argparse, ctypes, json, os, signal, sys, time
from boot_audit import require_boot_safe
from custom_image import prepare, STOCK_SHA, CUSTOM_SHA, SECTORS, DEST, NAME
from custom_runtime import validate_templates, program_preserving_storage
from flash_stock import Transport, ROOT, require, digest
TARGET_SHA = CUSTOM_SHA

def candidate_application():
    return (DEST/'app.bin').read_bytes()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['check', 'install', 'restore'])
    args = parser.parse_args()
    stock, target, manifest = prepare()
    validate_templates(stock, target)
    require(digest(stock) == STOCK_SHA and digest(target) == TARGET_SHA,
            'Build differs from reviewed custom image; no USB access')
    require(manifest['changed_sectors'] == SECTORS, 'Unexpected sector set')
    # Restore must remain available even when the custom application cannot boot.
    if args.mode in ('check', 'install'):
        require_boot_safe(candidate_application())
    if args.mode == 'check':
        print(f'Offline image checks passed for {NAME}. No USB access. Hardware validation pending.')
        return
    output = ROOT / ('custom-flash-' + NAME + '-' + time.strftime('%Y%m%d-%H%M%S'))
    output.mkdir(); owner = ROOT.stat().st_uid
    if os.geteuid() == 0: os.chown(output, owner, -1)
    log = (output/'operation.log').open('w', buffering=1)
    class Tee:
        def __init__(self, stream): self.stream = stream
        def write(self, s): self.stream.write(s); log.write(s)
        def flush(self): self.stream.flush(); log.flush()
    sys.stdout = Tee(sys.stdout); sys.stderr = Tee(sys.stderr)
    print('Output:', output, flush=True)
    print('Device:', NAME, 'Operation:', args.mode, flush=True)
    native = ctypes.CDLL(str(ROOT/'native-usb.dylib'))
    native.gb_error.restype = ctypes.c_char_p
    native.gb_transfer.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    signal.alarm(2100); deadline = time.monotonic() + 1800; opened = False
    try:
        print('Waiting up to 30 minutes for update mode (Pairing+B for two seconds).', flush=True)
        while True:
            code = native.gb_open()
            if code == 0: opened = True; break
            require(code == -2, native.gb_error().decode())
            require(time.monotonic() < deadline, 'Timed out waiting for controller')
            time.sleep(0.25)
        device = Transport(native, manifest['changed_sectors']); device.initialize()
        def save_artifact(name, data):
            with (output/name).open('xb') as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
        report = program_preserving_storage(device, stock, target, args.mode, save_artifact)
        report.update(hardware_functional_test='pending')
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print('FLASH VERIFIED:', report['sha256'], flush=True)
        print('Power-cycle, verify normal HID, then test AE42 notifications.', flush=True)
    finally:
        if opened: native.gb_close()
        for p in output.iterdir():
            if os.geteuid() == 0: os.chown(p, owner, -1)
if __name__ == '__main__': main()
