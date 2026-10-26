# Custom firmware test and restore

**Current status:** Do not install this custom candidate again. After the verified write, the user reported repeating white triple-blinks and no response to controls; BLE scans found no controller. The [failure audit](boot-failure.md) confirmed an execution-limit violation and a branch into the middle of a patched instruction. `check` and `install` now reject it before USB access; `restore` remains available. Use the stock restore command below; hardware recovery is pending. See [observations](evidence/custom-boot-observation.json).

2026-10-25. The custom firmware was installed: seven sectors and full flash readback verified. It adds a six-button AE42 stream to the official firmware. Initial functional checks failed; HID, button notifications and iOS behavior have not been validated. See [installation evidence](evidence/custom-install-result.json).

| Item | Value |
| --- | --- |
| Canonical stock template SHA256 | `dfbaeffd4e4cb2c940481cab918b55e29c2eea47107e3214ed12af96b03e8465` |
| Canonical custom template SHA256 | `b0c1bdf013ba35a0ad86fc1104412ab788da2bd294e47c0e644f6aaec8298ad8` |
| Custom app SHA256 | `8b3cf5bff313e27c4da630bf8759df7217f8a8ed88bcbf83d18c280c09b43221` |
| Changed 4 KiB sectors | `0x02000`, `0x06000`, `0x07000`, `0x0d000`, `0x11000`, `0x32000`, `0x33000` |
| Payload | 376 bytes; app grows by 408 bytes including alignment |

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

## Install blocked

There is no installable custom candidate. The offline command below must reject the current image:

```sh
.venv/bin/python research/flash_custom.py check
```

Do not bypass the guard. Keep the successful-install artifacts in `research/custom-flash-20261025-135838/` for analysis and restoration. Complete the [failure prevention plan](boot-failure.md) before preparing another image. The following button procedure applies only after a future candidate boots successfully.

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

Enter update mode as above. This restores the stock application installed on 2026-10-23, not the older factory application. Restore preserves VM, BTIF and USERIF from two matching live reads. Recovery permits partially written contents in the seven selected sectors but requires every remaining byte to match the stock template, including key/MAC. It refuses unidentified changes elsewhere. All 112 possible programmed-page failures were recovered in a NOR model; recovery from a nonbooting controller has not been tested on hardware.

Implementation and evidence: [custom firmware](custom-firmware.md), [image manifest](evidence/custom-image.json), [independent extraction](evidence/custom-extraction.json).
