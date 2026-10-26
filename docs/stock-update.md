# Install the official application

Status: installed on 2026-10-23. All 50 selected sectors and the entire flash readback matched the intended image. USB subsequently enumerated as LiteEMF / Hid Gamepade. Pairing and button tests remain pending.

Local operation records: `research/stock-flash-20261023-222601/`; version-control evidence: [stock-install-result.json](evidence/stock-install-result.json).

The user requested installing the downloaded IINE firmware before continuing custom BLE work. The application bytes are unmodified and match the official update SHA256 `2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259`.

This uses a custom host writer, not IINE's Windows updater. It transplants the official application into the installed flash layout. The installed file table retains its partition entries; application size/CRC, config offset and application-area CRC are updated, and identical config/P11 payloads move within the active area. It does not install the OEM single-area partition map or add its EXIF partition. Compatibility of that retained layout with the new application remains a hardware-test question.

The OEM and installed bootloader, chip configuration, cfg_tool and P11 files match exactly. The first application is 2,600 bytes larger in the update. The prepared 512 KiB image changes 50 sectors at `0x2000` through `0x33000`; all bytes before `0x2020` and after `0x33cd9` are unchanged. The full image SHA256 is `dfbaeffd4e4cb2c940481cab918b55e29c2eea47107e3214ed12af96b03e8465`.

## Checks completed

- Exact roundtrip of the original image when rebuilding with its existing app.
- Independent unpack of the prepared image; app, config, P11, bootloader and chip configuration match their official counterparts exactly.
- Original full-flash backup copies still match their recorded hash.
- Simulated NOR tests cover install, no-op repeat, exact restore, interrupted-write recovery, device-data mismatch, failed erase, failure to save the pre-write read, command/address bounds and an oversized app.

USB erase/program commands have now completed successfully on this device. Full readback verified the resulting image. Functional pairing and button compatibility have not yet been tested.

## Install

Run in an interactive terminal so macOS can authorize removable-storage access:

```sh
cd ~/dev/glassly-mini-gamepad
sudo .venv/bin/python -u research/flash_stock.py install
```

If waiting, power on with USB connected, then hold Pairing+B for two seconds until the light goes out. Release both and keep USB connected. The writer verifies BD19 and JEDEC CD7113, verifies the RAM loader, reads all flash, requires an exact match to the original backup, and saves that read before enabling writes. It erases/programs only the selected sectors, verifies each, writes the application-header sector last, then verifies the entire flash. It never sends chip-erase or fuse/key programming commands.

Success prints `FLASH VERIFIED` and the intended hash. Power-cycle and test pairing and all buttons. Check the added reader mode (Pairing+Up) separately. Stock firmware does not itself establish vendor button notifications or iOS background support.

## Restore

```sh
sudo .venv/bin/python -u research/flash_stock.py restore
```

Restore requires the USB bootloader to be accessible and every sector outside the update range to still match the original backup. It tolerates partially written update sectors, restores their original bytes and verifies the full original image. If normal runtime has changed VM/pairing data, restore deliberately stops for review instead of overwriting it. If firmware failure prevents entering the USB bootloader, wired recovery may be needed; a physical recovery method has not yet been validated.

Logs and pre-write reads are saved under `research/stock-flash-*/`. The original backups are never modified. See `stock-update-manifest.json` for the changed-sector list.
