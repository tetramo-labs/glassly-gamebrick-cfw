# Resources

Exact upstream revisions are in `../sources.lock.json`. Local copies retain their own license files. Firmware and device dumps are preserved locally and ignored by Git.

| Resource | Purpose |
| --- | --- |
| [IINE product](https://iine.store/products/iine-gamebrick-mini-retro-controller?variant=47068517302427) | User's controller |
| [IINE Chinese product](https://www.iine.top/products/mi-ni-kong-zhi-qi) | Official reader-update download |
| [Official update ZIP](https://media.iine.top/legacy-assets/6dd5d46599c6e1eeb8bd2623c15d14c7a3aee61163f46da0df38953c690dac61-zip) | OEM update, Windows updater and instructions |
| [Manual guide](https://iine.store/pages/gamebrick-mini-retro-controller-guide-manual) | Mode reference; local PDF in `research/manual.pdf` |
| [Jieli SDK](https://github.com/Jieli-Tech/fw-AC63_BT_SDK) | BD19 source reference and official RAM loader |
| [jl-misctools](https://github.com/kagaimiq/jl-misctools) | UFW/JLFS decoding, ciphers and checksums |
| [jl-uboot-tool](https://github.com/kagaimiq/jl-uboot-tool) | Bootloader protocol and loader blobs |
| [ghidra-jieli](https://github.com/quarkslab/ghidra-jieli) | Q32S and pi32v2 processor definitions |
| [LiteEMF](https://github.com/LiteEMF/LiteEMF) | HID/vendor protocol reference |
| [REA](https://github.com/morluto/rea) | Requested reverse-engineering workflow/tooling |
| [ElectronicCats research](https://github.com/ElectronicCats/jieli-ble-badge-research/tree/main/tools/ufw-repack) | Preserved reference-repack/reference-swap scripts; different chip, not directly applicable |
| [Apple GC background property](https://developer.apple.com/documentation/gamecontroller/gccontroller/shouldmonitorbackgroundevents) | GameController background constraints |

Official ZIP SHA256: `6dd5d46599c6e1eeb8bd2623c15d14c7a3aee61163f46da0df38953c690dac61`.
BD19 loader SHA256: `faa1b519a3ff1b082f11ccafac8c73d31150161ac972ef9f1934002bcbb8df4f`; the tool's copy matches the official SDK copy.

## Files

- `research/backup-controller-native.py`, `native-usb.m`: working Mac backup path.
- `research/build-app-patch.py`, `patch-flash.py`, `test-mirror-abi.py`: OEM-only prototype and offline checks.
- `research/disasm.py`, `find-calls.py`, `inspect-ufw.py`, `extract-ufw.py`: scratch analysis helpers. Disassembly defaults to the downloaded OEM app.
- `firmware/`, `scripts/check-custom.sh`, `research/custom_image.py`, `flash_custom.py`: queued AE42 payload, offline checks, retained-layout packaging and exact-build installer/restore.
- `research/custom_runtime.py`, `test_custom_runtime.py`: live storage preservation, immutable firmware checks and recovery fault tests.
- `probes/gamebrick-vendor.swift`, `GamebrickCapture.swift`, `scripts/build-vendor-probe.sh`: bounded AE42-only JSONL capture and physical input coverage checks.
- `probes/GamebrickPacket.swift`: custom packet decoder; compiled together with `gamebrick-listen.swift` by the check script.
- `probes/`: Swift BLE/GameController probes. `gamebrick-modes.swift` uses `/tmp/gamebrick-stop` as a stop sentinel; remove that sentinel before running it.
- `research/device-backup-20261022-233350/`: verified original flash and unpacked files.
- `research/STATUS.txt`: original chronology, including corrected assumptions. Use `docs/findings.md` for current conclusions.
- `artifact-manifest.json`: SHA256 inventory of preserved files at migration time, excluding upstream Git metadata and caches. Rebuilt outputs may differ from that snapshot.
