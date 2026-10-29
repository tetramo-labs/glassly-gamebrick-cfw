# Firmware and integration plan

Status: active. The first unit is stuck in a reset loop after the withdrawn custom image; see [failure analysis](boot-failure.md) and [recovery](recovery.md). The replacement candidate fixing both defects is installed on the second unit (unit2) and boots; its AE42 stream delivered all six buttons on a Mac on 2026-10-28. Longer term, the per-unit registration should become a single tool that takes any factory Gamebrick straight to the custom image without the intermediate stock step. Objective: expose all six controller buttons over a vendor BLE notification path usable by the Glassly App on iOS.

## Completed

- [x] Read the manual and identify controller modes.
- [x] Test normal HID and both vendor BLE notification channels.
- [x] Obtain and unpack the official reader update.
- [x] Build an offline patch prototype for that exact OEM application.
- [x] Establish native macOS USB access and verify the BD19 RAM loader.
- [x] Read the full installed flash twice and verify matching hashes.
- [x] Unpack the installed application and identify its differences from the OEM update.
- [x] Preserve resources in this repository.
- [x] Download and use REA; record supported results and Q32S limits.

## Stock application update

The user requested installing the downloaded firmware first. Installation completed on 2026-10-23; all 50 changed sectors and full-flash readback passed. USB gamepad enumeration returned. Pairing, power-cycle and button tests remain pending. See [stock-update.md](stock-update.md). Static analysis and read-only USB queries continued at the user’s request; keep the physical baseline tests pending.

## Installed-image analysis

1. REA 6.7.0 was installed and used for package inventory; see `docs/rea.md`. Raw Q32S analysis is unsupported. Continue with the existing Jieli SLEIGH/pypcode tools or scope explicit REA support.
2. Completed: Ghidra Q32S import, RAM relocation, GATT profile, HID/ATT/vendor senders and vendor command paths. Nine GET queries verified over USB. See `docs/q32s.md`. GPIO scanning and debounce are now reconstructed and checked against stock P-code. All 85 previous constructor failures decode. A complete offline AE42 candidate builds with task/lifecycle hooks and a 16-state queue; see `docs/custom-firmware.md`. Physical mapping confirmation and remaining report paths are pending.
3. Verify whether an existing command can enable vendor button reports without a firmware patch. B4/B5 and MessagePack configuration are established; no button-stream enable command has been established. Opcode 0x12 remains untested. Do not infer its semantics solely from upstream LiteEMF.
4. Stock update boundaries and a guarded restore writer are implemented. Physical recovery after an unbootable application remains untested. The custom installer preserves declared runtime storage; the older stock-only writer retains its original full-image guard.

## Patch and flash

- [x] Capture debounced keys from the periodic task before dependence on HID readiness.
- [x] Reserve task-stack state, queue 16 transitions and reset on CCC/BLE lifecycle changes.
- [x] Lock stock/payload hashes, patch bytes and branch targets; exercise compiled hooks in the bounded P-code model.
- [x] Repack the retained device layout and independently unpack it. Preserve unrelated bytes, config and P11 content.
- [x] Add `flash_custom.py` with exact-build/identity checks, seven-sector writes, full readback and stock restore. Inject/recover failures at each of 112 programmed pages offline.
- [x] Prepare an AE42-only JSONL probe with isolated press/release coverage and reconnect-baseline checks. Current bounded scans found no matching BLE peripheral.
- [x] Install custom firmware from the user's interactive terminal; seven sectors and full readback verified on 2026-10-25. Physical stock baseline tests were not confirmed before this flash.
- [x] Reproduce both defects in the captured flashed image, add eight boot regression tests, and reject installation before USB access while retaining stock restore.
- [x] Fix both defects (limit raised with placement at `0x01e10a90`; hook moved to `0x01e05270`) and extend the audit to reject either regression. Application-independent recovery is still undemonstrated; the user accepted that risk for unit2.
- [x] Derive images per unit from each unit's own backup (`research/devices.json`, `add_device.py`); stock installer preserves live runtime storage.
- [x] unit2: register backup, install stock, confirm buttons/pairing physically (2026-10-28).
- [x] unit2: install the replacement custom image; boots, USB enumerates, AE42 delivers all six buttons with press/release on a Mac (2026-10-28).
- [x] One-shot flasher `flash_gamebrick.py` (factory or official firmware straight to Glassly, restore to official), offline tests, setup script that fetches pinned dependencies, README for end users (2026-10-28).
- [x] Glassly App driver for iOS and Android (`IINE Gamebrick`, source 5): D-pad swipes, A hold-aware tap lifecycle, B double tap; pairing guide links this repository.
- [ ] unit2: confirm USB HID and C-mode BLE HID under the custom image; explain the early BLE disconnect; test other modes, reconnect, unsubscribe and standby/wake; test the Glassly App driver on a phone, including iOS background.
- [ ] Package the flasher as a signed macOS app; Windows/Linux transports.
- [ ] unit1: wired recovery remains pending; `flash_custom.py restore` under `GB_DEVICE=unit1` once update mode is reachable.

See `docs/custom-install.md` for the concrete commands and reviewed hashes. The first two custom install attempts stopped before writes: the first on 38 changed VM bytes and the second on one additional USERIF byte. The firmware is unchanged. `custom_runtime.py` now checks two matching full reads, preserves declared VM/BTIF/USERIF storage and rejects all other unexpected changes. It saves the source, restore image, target and preflight report before writes. Offline tests cover both captures and all 112 page failures; the third attempt completed with full readback SHA256 `bec28bd21195de6d5ef50a0fb163a5dd8d669aeba2aa38e79b8ca37a2cc2073b`. See [installation evidence](evidence/custom-install-result.json).

## Hardware and Glassly validation

1. Verify normal USB/Bluetooth HID still works, all six buttons notify correctly, release states arrive, and pairing/configuration survive reboot.
2. Add native CoreBluetooth support in the Glassly repo, following its mobile guidelines. Confirm service discovery, subscription, reconnect, state restoration and event delivery.
3. Test an actual iPhone with the Glassly App foregrounded, backgrounded and the screen locked. Record delivery, latency and reconnect behavior. Mac tests do not establish iOS behavior.
4. Document the tested hardware/firmware version, button protocol, installation/recovery commands and remaining limitations.

Do not flash `research/candidate/*.bin`: those are OEM-version prototypes. The retained-layout candidate under `research/custom-prepared/` is withdrawn and blocked by the boot audit. Preserve it for analysis and restoration.
