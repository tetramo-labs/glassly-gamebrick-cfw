# Custom firmware test and restore

**Current status (2026-10-28):** The replacement candidate, which fixes both confirmed defects of the withdrawn 2026-10-25 image, is installed on unit2 and boots. Stock was installed and confirmed physically first; the custom image then enumerated over USB, answered vendor queries, and delivered all six buttons with press and release over AE42 to a Mac (`evidence/ae42-validation-unit2-1.jsonl`). The first unit remains in its reset loop. See [failure analysis and the fix](boot-failure.md).

Images are derived per unit from that unit's own verified backup, because the key/MAC sector and runtime storage differ between controllers. `research/devices.json` records each unit's backup directory and its pinned original, stock and custom hashes; `GB_DEVICE` selects a unit for the historical regressions. `research/add_device.py` registers a new unit after checking that its factory application, bootloader, configuration and partition map match the analysed unit and that only runtime storage and key/MAC differ.

| Item | Value |
| --- | --- |
| Payload | 380 bytes; app grows by 408 bytes including alignment |
| Changed 4 KiB sectors (stock to custom, every unit) | `0x02000`, `0x06000`, `0x07000`, `0x0d000`, `0x11000`, `0x12000`, `0x32000`, `0x33000` |
| unit1 stock template SHA256 | `dfbaeffd4e4cb2c940481cab918b55e29c2eea47107e3214ed12af96b03e8465` |
| unit1 replacement custom SHA256 | `e3e67d34f6bc06ed98e6181fe65316457c646152f5d27b6e0467175109fdd9fd` |
| Withdrawn unit1 custom SHA256 (do not install) | `b0c1bdf013ba35a0ad86fc1104412ab788da2bd294e47c0e644f6aaec8298ad8` |

Per-unit hashes live in `research/devices.json`; the custom application itself is the same for every unit, only the surrounding flash image differs.

The writer checks the exact build, BD19/UBOOT identity, flash ID and RAM loader. It requires two identical full flash reads and verifies every byte outside the declared runtime storage against the pinned templates. It saves the complete pre-write image, stock restore image, target and preflight report before erasing. It writes only the seven selected sectors, commits the active header last and verifies the entire final flash. The update is not atomic across power loss.

## Runtime storage

The first attempt on October 24 stopped before writes on 38 changed bytes in VM. The October 25 retry stopped on one further change at `0x7d001` (`0x72` to `0x00`) in USERIF. Both captures contain the exact stock firmware. The changed fields' meanings are unknown.

The snapshot-specific fix in `custom_baseline.py` was too restrictive. The live installer now uses `custom_runtime.py`, which validates the reserved partition records and preserves these regions from its matching live reads:

| Region | Inclusive flash range |
| --- | --- |
| VM | `0x7a000..0x7bfff` |
| BTIF | `0x7c000..0x7cfff` |
| USERIF | `0x7d000..0x7efff` |

These sectors are never erased or programmed. The bootloader, application, partition map, inactive area and key/MAC sector remain exact-match requirements. No force option is provided. The final target hash depends on current storage and is recorded in `preflight.json` and verified after writing.

Tests cover both actual captures, changes outside these regions, mismatching reads, failed artifact saves and recovery from all 112 programmed-page failures with variable storage. See [runtime evidence](evidence/custom-runtime.json). The older [baseline evidence](evidence/custom-baseline.json) records the superseded October 24 snapshot approach. Hardware validation remains pending.

## One-shot flasher

`research/flash_gamebrick.py install` is the end-user path and the one the README documents: it reads the flash twice, keeps the reads as a backup, classifies the contents by a storage-independent fingerprint (factory `62153ccb…`, official update `dc16ee8a…`, Glassly `c482ad55…`), derives the Glassly image from that read plus the committed applications in `firmware/dist` (official `2fb44f42…`, Glassly `495ce913…`, both hash-checked on every run; `--oem-zip` rebuilds them from IINE's archive through the independent unpacker and the reviewed patch instead), writes only the changed sectors and verifies the whole flash. `restore` derives the official image the same way from any known state. Unknown contents, including the withdrawn 2026-10-25 image, are refused before writes. `research/test_flasher.py` exercises every state transition against the unit2 artifacts. The per-unit workflow below remains the research path with explicit stock and custom steps.

## Register a unit and install

1. Back up read-only from your own terminal: `sudo .venv/bin/python -u research/backup-controller-native.py`. Enter update mode with Pairing+B held for two seconds after powering on with USB connected.
2. Register: `.venv/bin/python research/add_device.py <name> <device-backup-dir> --write`. It stops on any difference outside runtime storage and key/MAC, or on an unanalysed application version.
3. Rebuild and verify: `./scripts/check-custom.sh`. It must end with `flash_custom.py check` passing for the current unit and the historical unit1 regressions still reproducing the withdrawn failure.
4. Install the official application first and test buttons and pairing physically: `sudo .venv/bin/python -u research/flash_stock.py install`. The stock writer now reads twice, preserves live VM/BTIF/USERIF and requires every other byte to match the registered backup.
5. Install the custom image: `sudo .venv/bin/python -u research/flash_custom.py install`. It audits the candidate before opening USB, requires the unit to hold its exact stock image outside runtime storage, writes the eight sectors with the header last and verifies the whole flash.

Keep the unit1 artifacts in `research/custom-flash-20261025-135838/` for analysis. Application-independent recovery is still not demonstrated; a non-booting custom image still means wired recovery. The button procedure below applies after the custom image boots.

## Button validation

Build the AE42-only probe, then capture a bounded session:

```sh
./scripts/build-vendor-probe.sh
research/q32s-analysis/gamebrick-vendor 150 | tee research/custom-prepared/ble-validation.jsonl
```

The probe uses CoreBluetooth, discovers only AE40 and subscribes only to AE42. It does not import or use GameController. It recognizes IINE/Gamebrick names or manufacturer data, and can reuse a unique already-connected matching AE40 peripheral. For an explicit observed device, append its UUID after the duration. Duration is limited to 1–600 seconds.

Press/release Up, Down, Left, Right, A and B separately, then test combinations. Each JSON `buttons` record includes held/pressed/released state, sequence and overflow. The final summary reports isolated press/release coverage for all six bits. Reconnection baselines are not counted as physical presses; a gap or overflow invalidates the pending isolated-release check. A disconnect does not synthesize a release or prove zero held buttons. Match the logged names against the physical labels, especially A/B.

The summary's `all_six_press_release_observed` measures observed bit transitions only. It does not establish normal HID operation, iOS background delivery, or absence of a separate OS HID connection. `ios_background_verified` remains false. Preserve the full JSONL, including subscription and disconnect events.

Verify normal USB/Bluetooth HID separately, then repeat reconnect, unsubscribe/resubscribe and standby/wake. The older `gamebrick-listen` probe is retained for combined HID/vendor diagnostics; use the AE42-only probe for vendor evidence.

## Restore stock

```sh
cd ~/dev/glassly-mini-gamepad
sudo .venv/bin/python -u research/flash_custom.py restore
```

Enter update mode as above. This restores the current unit's official application image, not the factory application. Restore preserves VM, BTIF and USERIF from two matching live reads. Recovery permits partially written contents in the eight selected sectors but requires every remaining byte to match the unit's stock template, including key/MAC. It refuses unidentified changes elsewhere. All 128 possible programmed-page failures were recovered in a NOR model; recovery from a nonbooting controller has not been tested on hardware. `flash_stock.py restore` returns a unit to its registered factory backup, again preserving live runtime storage.

Implementation and evidence: [custom firmware](custom-firmware.md), per-unit image manifests `evidence/custom-image-<unit>.json` and independent extractions `evidence/custom-extraction-<unit>.json`.
