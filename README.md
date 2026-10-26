# Glassly Mini Gamepad

Firmware research for the IINE Gamebrick Mini Retro Controller L1161/L1162. The target is button notifications over a vendor BLE characteristic that the Glassly App can receive on iOS in the background.

**Status:** The custom firmware passed flash readback on 2026-10-25 but failed initial functional checks: the user reports continuous white triple-blinking and unresponsive controls, and BLE scans found no controller. The audit found code outside the CPU execution limits and a branch into the middle of a patched instruction. Installation is blocked. See [failure analysis](docs/boot-failure.md) and [hardware recovery](docs/recovery.md).

- [Current findings](docs/findings.md)
- [Implementation plan](docs/plan.md)
- [Tools and sources](docs/resources.md)
- [Backup metadata](docs/device-backup.json)
- [REA investigation](docs/rea.md)

## Local setup

This checkout includes local copies of the firmware, backups and upstream tools under `research/`. They are ignored by Git; a Git clone alone will not contain them. `sources.lock.json` records upstream revisions and `artifact-manifest.json` inventories the preserved research files. Third-party sources retain their licenses.

```sh
cd ~/dev/glassly-mini-gamepad
./scripts/setup.sh
.venv/bin/python scripts/verify-backup.py
```

The setup script creates an isolated Python environment, builds the native macOS USB transport, and compiles the Q32S SLEIGH description. It does not connect to hardware.

## REA

REA 6.7.0 is installed locally. Run `./scripts/rea.sh --help`. It successfully inventories the OEM ZIP but does not support this raw Q32S application; see [the recorded results](docs/rea.md).

## Take another backup

Run from an interactive terminal so macOS can present its Removable Volumes permission prompt:

```sh
sudo .venv/bin/python -u research/backup-controller-native.py
```

With the controller powered on and USB connected, hold Pairing+B for two seconds until the light goes out. Release both buttons and leave USB connected. The helper waits up to 30 minutes, verifies a RAM loader, reads the entire flash twice, and compares SHA256 hashes. Its command allowlist excludes flash programming, erase and fuse writes.

The older libusb helper is retained for reference; it failed to open the interface on this Mac. Background administrator launches also failed because the removable-storage permission request could not reach the login session.

## Offline prototype

```sh
.venv/bin/python research/build-app-patch.py
.venv/bin/python research/test-mirror-abi.py
.venv/bin/python research/patch-flash.py
```

These commands operate on the **downloaded OEM update**, not the installed firmware. They produce experimental raw images, not a complete installable UFW. The ABI check is a simulated-call regression check, not hardware validation.

## Q32S analysis

[Verified vendor protocol, RAM/HID path and configuration reads](docs/q32s.md). The stock firmware responds to B4/B5 MessagePack queries; all nine GET groups were read over USB. The GPIO scanner/debounce logic is reconstructed. A 376-byte custom payload now has task/lifecycle hooks, a 16-state queue, device-layout packaging and a guarded installer. The new boot audit rejects this candidate; earlier model checks missed two boot/control-flow defects. See [install/restore commands](docs/custom-install.md). See [custom firmware](docs/custom-firmware.md) and [decoder/toolchain work](docs/q32s-decoder.md).
