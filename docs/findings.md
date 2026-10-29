# Findings

Updated 2026-10-28. See the final section for the replacement candidate and the second unit. Earlier text describes the first unit (unit1).

Earlier status (2026-10-25). The custom 376-byte AE42 payload is installed. All seven written sectors and full flash readback passed, preserving current device storage. Final SHA256: `bec28bd21195de6d5ef50a0fb163a5dd8d669aeba2aa38e79b8ca37a2cc2073b`. Initial functional checks failed. The boot audit confirmed two patch defects and now blocks installation; see [failure analysis](boot-failure.md). Hardware recovery and subsequent HID/BLE/iOS validation remain pending. The backup below is the original pre-update image.

## Device

| Item | Observed value |
| --- | --- |
| Product | IINE Gamebrick Mini Retro Controller L1161/L1162 |
| Normal USB | LiteEMF / Hid Gamepade, VID:PID `4353:8009` |
| Update USB | BR34UBOOT1.00, VID:PID `4c4a:3442` |
| SCSI identity | **BD19 / UBOOT1.00** |
| CPU family | BD19 / AC632N, Q32S; BD19 RAM loader upload, readback and execution succeeded |
| Flash | JEDEC `cd7113`, 524,288 bytes |
| Application entry | `0x01e00120` |

The USB product string initially suggested BR34. Direct SCSI identification and successful BD19 loader execution supersede that inference.

## Verified original backup

Location: `research/device-backup-20261022-233350/`.

Both `flash-pass1.bin` and `flash-pass2.bin` are 524,288 bytes and have SHA256:

```text
9b7c57387ded72fadd162599cfb2b3797fb27e10759918d4e06f879740577cb3
```

The unpacker extracted a 196,224-byte installed application with SHA256:

```text
902aedc30a84c9ae777e3cbdd12ff5737ac17b7ee3f5288f76c7aa86fe267c97
```

The downloaded OEM update contains a different 198,824-byte application (`2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259`). Its patch offsets and raw image layout must not be applied directly to the backup.

The original image declares `app_dir_head` at `0x2020`, a second area at `0x3e020`, and `key_mac` at `0x7f000`. The application header is at `0x2020`, its file table at `0x2040`, and application bytes at `0x2140`. VM, PRCT, BTIF and USERIF entries are also present. The stock update retained these entries and special VM/BTIF/USERIF records; its changed sectors and full readback were verified. See `stock-update.md` for the validated update boundaries.

## BLE observations

C mode advertises Xbox Wireless Controller; all six inputs worked through macOS GameController. H mode advertises IINE_keyboard; T mode advertises IINE_control. Alternate modes are described in the preserved manual.

All three tested modes expose Device Information, Battery, AE40 (AE41 write-without-response, AE42 notify) and AE00 (AE01 write-without-response, AE02 notify). Subscribing and pressing Up, Down, Left, Right, A and B produced no button reports on the vendor channels. AE02 sent a single `ff`; SDK code identifies this as RCSP availability, not a button event.

Device Information reports `zhuhai_jieli`, model `hid_mouse`, revisions `0.0.1`. These generic revision strings do not identify the installed binary. Advertising manufacturer bytes included `41ff6d745f49494e45` (`mt_IINE`).

Normal USB has a gamepad HID interface and a 64-byte vendor HID interface (usage page FF80). Read-only LiteEMF queries in A4/A5 framing returned no replies. Test-mode command 0x12 was found in LiteEMF source but was not sent.

## Q32S analysis and live vendor protocol

See [q32s.md](q32s.md) for the address map, GATT profile, tools and raw evidence. The installed application's vendor interface uses B4/B5 frames with MessagePack command `0xcc`. All nine GET queries succeeded over USB; the controller reports version `0x0300` and model `mt_IINE`. Keyboard, mouse, consumer, touch, sleep and screen settings were decoded. XInput/DInput queries returned empty maps.

The transmit router executes from RAM `0x4c62`, copied from the end of the application. Its call at `0x4d10` reaches the HID sender at `0x01e0420c`; the vendor call at `0x4dc2` reaches `0x01e06180`. GATT handles are AE41 `0x52`, AE42 `0x54`/CCC `0x55`, AE01 `0x82`, AE02 `0x84`/CCC `0x85`.

## Prototype and limits

The prototype targets the same application hash now installed, but its OEM raw-image packaging does not match the retained device layout. Do not flash that image. The candidate redirects one HID send call to an untested wrapper that mirrors payloads to AE42 without a report ID.

The newly traced RAM router gates the HID call on HID readiness. A vendor-only connection may never reach that hook. Revise the capture point or demonstrate that this gate permits vendor-only operation; use a defined report format and independent vendor CCC/backpressure handling.

The isolated Q32S processor now decodes all 85 previous constructor-failure sites, with lengths matching the official disassembler. Other P-code/type/flow errors remain. The GPIO scanner and two-sample debounce are reconstructed in C and match a stock P-code model across 512 samples. The 376-byte custom AE42 payload now includes task/CCC/lifecycle hooks and a 16-state queue. State is reserved on the task stack; a four-byte reset counter occupies BSS alignment padding. Device-layout packaging changes seven sectors. Compiled-hook simulation, independent unpacking and failure/recovery checks at all 112 programmed pages pass offline. The current candidate is withdrawn and the boot audit blocks installation; see [install and restore](custom-install.md). See [custom firmware](custom-firmware.md) and [decoder limits](q32s-decoder.md). Five existing protocol regression checks also pass. The custom patch was flashed on October 25; no Glassly driver has been added; pairing/all physical inputs and iOS background behavior remain untested after the update.

## Transport lessons

Apple's native IOUSBHost API works when the helper runs with sudo from the user's terminal. libusb interface opening failed on macOS 27.0.1. A background administrator launch failed the Removable Volumes privacy check even with root privileges.

FC0A returns the full flash ID as a little-endian uint32 at response payload bytes 2–5. FC0B returns that ID shifted right eight bits, omitting density. The backup helper now cross-checks both replies and uses FC0A's low byte for capacity. The captured response decodes to CD7113 / 512 KiB.

## 2026-10-24 validation preparation

No custom-flash result directory or running flash helper was found. USB still enumerates as `Hid Gamepade`; this does not identify its application bytes. Two bounded 30-second BLE checks found no matching advertisement or already-connected AE40 peripheral and received no notifications. Bluetooth access was authorized and powered on. See [scan evidence](evidence/vendor-preflash-check.jsonl). These are discovery results, not failed button tests.

The new `gamebrick-vendor` probe discovers only AE40 and subscribes only to AE42, without GameController. Its JSONL tracks isolated presses/releases, sequence gaps, overflow and reconnect baselines. Capture/parser tests and invalid-argument checks pass. The next hardware step remains the interactive custom installation and physical button checks in [custom-install.md](custom-install.md).

## First custom install preflight

`research/custom-flash-20261024-102322/before.bin` is a complete BD19 readback with SHA256 `5ad0acbd772c309f6db2ea8f6f0263cd6fbc03d6e72a6e2c26ff1a4eb84d8ae3`. The installer rejected it before enabling writes. Only 38 bytes in sector `0x7a000` differ from the previous stock reference; the whole application, bootloader, partition map and remaining bytes match.

The reviewed target was rebased on this exact captured image, preserving those storage bytes. Its full-image hash is now `bec28bd21195de6d5ef50a0fb163a5dd8d669aeba2aa38e79b8ca37a2cc2073b`; the custom application and seven write sectors are unchanged. Exact source/target guards remain. Install/restore fault tests and independent unpack comparisons passed. See [retry instructions](custom-install.md) and [baseline evidence](evidence/custom-baseline.json). No custom write has been recorded.

## Second custom install preflight and storage preservation

The October 25 readback (`research/custom-flash-20261025-132431/before.bin`, SHA256 `7633d6fc7dafaaf90b31c2c701c0fd47389b8adc9427855d60e307993e386a9f`) differs from October 24 by one byte: `0x7d001`, `0x72` to `0x00`. The installer stopped before writes. The stock firmware remains exact; this byte lies in USERIF. Its field meaning has not been determined.

Checksum-validated file-table entries declare VM at `0x7a000` (8 KiB), BTIF at `0x7c000` (4 KiB) and USERIF at `0x7d000` (8 KiB). Key/MAC begins at `0x7f000` and is excluded. The pinned SDK's `cpu/bd19/tools/isd_config_rule.c` documents reserved regions and preserving them during download.

The live installer now preserves these three regions from two matching full reads. All other bytes must match the pinned stock or custom template on install. Recovery additionally permits partial writes only in the seven reviewed patch sectors. Both runtime images and the preflight report are saved before writes, and complete final readback must match the computed target. This supersedes the snapshot-specific October 24 installer. Offline tests pass for both captures, all 112 interrupted page writes, variable storage, immutable-byte rejection, unstable reads and failed saves. See [runtime evidence](evidence/custom-runtime.json). No custom hardware write has been recorded.

## Successful custom installation: 2026-10-25

`research/custom-flash-20261025-135838` contains the successful install. Two full preflight reads matched the October 24 stock capture (`5ad0acbd...`); USERIF had returned to its earlier value. The helper saved the source, stock restore image, target and report before writes. Seven sectors verified, with `0x2000` committed last, followed by full-device readback equality to `bec28bd21195de6d5ef50a0fb163a5dd8d669aeba2aa38e79b8ca37a2cc2073b`. Saved artifacts were independently rehashed and their differences restricted to those seven sectors. VM, BTIF, USERIF and key/MAC were preserved.

See [installation evidence](evidence/custom-install-result.json). This establishes installation/readback success; boot, HID, AE42 input and iOS background behavior remain pending.

## Post-flash failure report

The user reports continuous white LED triple-blinks separated by a pause, regardless of controls. The first completed vendor scan received no controller advertisements or packets; a separate unfiltered BLE scan also found no named IINE/Gamebrick/Xbox controller. No controller was enumerated over USB at the latest check, but cable connection was not confirmed. These observations suggest a reset loop or other startup fault; they do not identify the failing instruction or establish the LED pattern's meaning.

The 376-byte custom candidate is withdrawn from further installation. Restore official stock first using `flash_custom.py restore`, which preserves current VM/BTIF/USERIF data and only rewrites the seven patch sectors. Offline restoration of the exact installed target reproduced the saved stock restore image. Hardware restore remains pending. See [failure evidence](evidence/custom-boot-observation.json).

## Update mode unavailable

The user reports the suspected reset loop prevents flashing. A short USB enumeration poll did not observe either controller interface; cable connection was not confirmed during the poll. The current restore helper cannot force boot-ROM entry: it waits for the USB bootloader to enumerate. Jieli documents a hardware forced-upgrade handshake at reset. Board inspection and available programmer identification are now required before specifying a recovery connection. See [recovery investigation](recovery.md). No new writes or pin-short attempts were made.

## Confirmed patch defects: 2026-10-25

The application extracted from the saved flashed target has two confirmed defects. The payload at `0x01e309d0` is outside the enabled flash PC range ending at `0x01e2dfc8`. The actual exception path records `0xab` and requests a soft reset. Separately, the unchanged-state branch at `0x01e05256` still targets `0x01e05276`, now inside the new four-byte jump; its bytes decode as an unintended low-RAM write and fall through without restoring the stack. The model reproduces that path for states 0, 1 and 7.

This supports an exception/reset explanation for the reported repeating white triple-blinks, but no live crash trace or dedicated three-blink fault code has been established. Eight new regressions pass; `flash_custom.py check/install` now refuse before USB access, while simulated stock restoration of the captured target still passes. No firmware bytes were changed and no new image was flashed. See [full evidence and prevention plan](boot-failure.md).

## Replacement candidate and second unit: 2026-10-28

The first unit remains unrecovered. A second controller was obtained. The custom candidate was rebuilt to fix both confirmed defects: the flash text execution limit programmed by `debug_init` (immediate at `0x01e10a90`) is raised together with the payload placement to exactly the new application end, and the BLE hook moved to the register moves at `0x01e05270` so the stock call and epilogue, and the branch that targets the epilogue, are preserved. The payload is 380 bytes and the stock-to-custom change is eight sectors (`0x12000` added). The boot audit executes the real limit setup and now also rejects any limit that differs from the application end, any other range change and any change to the startup data copy. Twelve boot regressions pass; the withdrawn image still fails with four codes. Nothing has been flashed.

Images are now derived per unit. `research/devices.json` pins each unit's original, stock and custom image hashes; `research/add_device.py` registers a unit from its read-only backup after confirming the same factory application, bootloader, configuration and partition map, with differences confined to runtime storage and key/MAC. Re-deriving unit1 reproduces its pinned hashes. `flash_stock.py` now reads twice and carries live VM/BTIF/USERIF into both source and target, so storage drift after the backup no longer blocks the stock install. The plan for unit2 is stock first with physical confirmation, then the custom image.

## unit2 installed and validated on a Mac: 2026-10-28

unit2 backup `221856d2…` matched unit1's factory image everywhere outside runtime storage (463 VM bytes, 7 BTIF bytes); the key/MAC sector is blank on both units. The official application was installed first (50 sectors, final `51b28f43…`, storage unchanged), confirmed physically: normal LED, USB `Hid Gamepade`, vendor queries answering version `0x0300`/`mt_IINE`, C-mode pairing with all six buttons, and update-mode entry. The replacement custom image was then installed (eight sectors, final `f735d787…`, which is the pinned `e1dc827e…` with 38 live VM bytes preserved after pairing). Evidence: `evidence/stock-install-result-unit2.json`, `evidence/custom-install-result-unit2.json`, `evidence/custom-install-preflight-unit2.json`.

The custom image boots: normal orange LED, USB enumeration and vendor queries unchanged. An AE42-only CoreBluetooth capture in H mode (`IINE_keyboard`) received 100 packets with isolated press and release for all six buttons, combinations, no sequence gaps, no overflow and no unrecognized packets; firmware A/B labels match the physical buttons. One controller-initiated disconnect occurred about ten seconds after the first unbonded connection, with reconnection after thirteen seconds; its cause is not established. Evidence: `evidence/ae42-validation-unit2-1.jsonl`. USB HID and BLE HID regression under the custom image, other modes, standby/wake and iOS background delivery remain to be checked. This is a Mac test and does not establish iOS background support.
