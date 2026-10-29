#!/usr/bin/env python3
"""Install custom firmware or restore stock, preserving current runtime storage."""
import argparse, json, os, sys, time
from boot_audit import require_boot_safe
from custom_image import prepare, STOCK_SHA, CUSTOM_SHA, SECTORS, DEST, NAME
from custom_runtime import validate_templates, program_preserving_storage
from flash_stock import Transport, ROOT, require, digest
from usb_transport import open_link, wait_for_controller, update_mode_instructions, require_privileges, start_watchdog, give_back_ownership
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
    require_privileges()
    output = ROOT / ('custom-flash-' + NAME + '-' + time.strftime('%Y%m%d-%H%M%S'))
    output.mkdir(); give_back_ownership(output, ROOT)
    log = (output/'operation.log').open('w', buffering=1)
    class Tee:
        def __init__(self, stream): self.stream = stream
        def write(self, s): self.stream.write(s); log.write(s)
        def flush(self): self.stream.flush(); log.flush()
    sys.stdout = Tee(sys.stdout); sys.stderr = Tee(sys.stderr)
    print('Output:', output, flush=True)
    print('Device:', NAME, 'Operation:', args.mode, flush=True)
    link = open_link(); start_watchdog(2100)
    try:
        print('Waiting for the controller (up to 30 minutes).', flush=True); print(update_mode_instructions(), flush=True)
        wait_for_controller(link, time.monotonic() + 1800)
        device = Transport(link, manifest['changed_sectors']); device.initialize()
        def save_artifact(name, data):
            with (output/name).open('xb') as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
        report = program_preserving_storage(device, stock, target, args.mode, save_artifact)
        report.update(hardware_functional_test='pending')
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print('FLASH VERIFIED:', report['sha256'], flush=True)
        print('Power-cycle, verify normal HID, then test AE42 notifications.', flush=True)
    finally:
        link.close()
        give_back_ownership(output, ROOT)
if __name__ == '__main__': main()
