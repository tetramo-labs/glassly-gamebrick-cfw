# Custom firmware component

2026-10-24. Target application SHA256: `2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259`.

The custom candidate is built for the installed device layout. It adds AE42 button notifications while retaining the stock button scanner and HID paths. The 376-byte first payload was flashed on October 25 and failed initial functional checks: the [failure audit](boot-failure.md) found an execution-limit violation and an unchanged-state branch into the middle of a patched instruction. The 380-byte replacement of 2026-10-28 fixes both and passes the offline audit; it has not been flashed. See [install and restore](custom-install.md).

## Recovered input path

The routine at `0x01e0ce10` scans active-low inputs through the RAM GPIO reader at `0x4b1a`, which calls `0x01e04124`. GPIO numbering uses the BD19 SDK's 16-pin groups.

| GPIO | Port | Stock key mask | Logical input | Custom bit |
| --- | --- | --- | --- | --- |
| 19 | PB3 | `0x00000001` | A | 4 |
| 7 | PA7 | `0x00000002` | B | 5 |
| 22 | PB6 | `0x80401000` | HOME/FN/POWER aliases | Excluded |
| 23 | PB7 | `0x00010000` | Up | 0 |
| 0 | PA0 | `0x00020000` | Down | 1 |
| 24 | PB8 | `0x00040000` | Left | 2 |
| 25 | PB9 | `0x00080000` | Right | 3 |

A/B names come from firmware debug strings. Physical face-button correspondence still needs a capture after the stock update.

| RAM address | Meaning |
| --- | --- |
| `0x2adc` | Current tick counter |
| `0x2a7c` | Last scan tick |
| `0x2a8c` | Candidate raw keys |
| `0x2a90` | Stable keys |
| `0x2a78` | Exported current keys |
| `0x29e2` | BLE connection handle, 16 bits |

Scanning runs when unsigned `tick - last_scan >= 100`. Two consecutive matching samples establish the stable state; the exported state follows it. The periodic event path increments the counter by 100 before calling the handler. Timer setup has not been traced far enough to establish wall-clock timing.

The periodic task `0x01e0ee68` receives message class `0x01000000`, advances the tick counter and calls the button handler at `0x01e0f194`. This call is now wrapped: original processing runs first, then the custom stream reads debounced keys. No HID subscription gate surrounds this task call. Actual behavior in each physical mode remains to be tested.

## Hooks and storage

| Patch address | Change |
| --- | --- |
| `0x01e0bcac` | Task creation points to the custom initializer, which tail-jumps to the original task entry |
| `0x01e0bcb6` | Task stack request increases from `0x800` to `0x840` |
| `0x01e0f194` | Calls the original handler followed by the custom stream |
| `0x01e04b86` | Wraps the stock CCC setter; AE42 CCC writes advance a reset counter |
| `0x01e05270` | Replaces `r1 = r5; r2 = r4` before the BLE event call with a jump to a wrapper that performs those moves, calls the stock event through the epoch-advancing wrapper and pops the original frame. The stock call at `0x01e05274` and epilogue at `0x01e05276` are preserved, so the unchanged-state branch at `0x01e05256` stays valid. The withdrawn image hooked `0x01e05274` and overwrote that epilogue. |
| `0x01e10a90` | Raises the flash text execution limit programmed by `debug_init` from the linked text end `0x01e2dfc8` to exactly the new application end. Protection remains enabled; RAM/ROM ranges and the startup data copy are unchanged. |
| `0x01e00138` | Extends BSS clearing by four bytes for the reset counter |

The initializer reserves and clears 40 bytes before entering the stock task. Its original 88-byte frame is unchanged; custom state lives at task `sp+88`. The stock task has no return path, and its decoded stack accesses remain within offsets 0–87. Raising the stack request preserves the original headroom. No heap allocation is added.

The reset counter uses `0x40b8..0x40bb`. Startup declares BSS `0x1cc0..0x40b7` and copies RAM code starting at `0x40c0`; this reserves four bytes from their alignment gap. No existing direct reference to the reserved address was found. The boot-loop model verifies that clearing stops before the remaining padding and code. Static boundary/reference checks are not a hardware memory trace.

## Notification component

`firmware/vendor_stream.c` checks AE42 CCC `0x55` through `0x01e041b6`, then calls the stock ATT sender `0x01e034b4` with the checked connection, handle `0x54` and operation 0. Binding the connection explicitly avoids rereading it in the AE42 wrapper. The stock command `0x1a` path calls `0x01e13b5a`, which copies the packet into its transmit ring through `0x01e1b08a` before returning; a stack packet is therefore sufficient for that path.

Four-byte AE42 payload:

| Byte | Value |
| --- | --- |
| 0 | `0x47` (`G`) |
| 1 | Protocol version `1` |
| 2 | Sequence, wraps modulo 256 after accepted sends |
| 3 | Bits 0–5: Up, Down, Left, Right, A, B; bit 6: queue overflow; bit 7: zero |

This format is distinct from stock B4/B5 command frames. The stream sends an initial snapshot, state changes including releases, and a baseline after connection/subscription changes. A 16-entry queue retains transitions during temporary send failures, with one queued snapshot attempted per task tick. Sequence advances only after successful acceptance by the stock sender; this does not prove reception by the phone.

On queue overflow, the oldest unsent state is dropped and bit 6 is set on the next accepted snapshot. The latest state, including a release, is retained. Disconnects and subscription resets discard stale queued input. The BLE callback only updates the reset counter; queue storage is owned by the periodic task.

The payload begins at `0x01e309d0`, after the application's RAM data and RAM code images, and ends inside the raised execution limit. Its linker script rejects initialized data or unplaced BSS. Unused reconstructed scan code is removed by the linker because the component uses stock debounced keys. [Build manifest](evidence/q32s-payload.json) and [image manifest](evidence/custom-image.json) record hashes, patch bytes and changed sectors.

## Build and checks

Requires the pinned local toolchain, running Docker, macOS clang, the Python environment and compiled extended SLEIGH language. See [decoder/toolchain notes](q32s-decoder.md).

```sh
./scripts/check-custom.sh
```

Earlier checks below passed but missed the two defects. The boot regression suite (12 tests) detects the withdrawn image and passes the replacement under protected fetch; the installability check passes for the replacement. Images are built per registered unit (`research/devices.json`).

Historical checks:

- Recovered C matches stock scan-region P-code across 512 deterministic samples, including bounce, skipped scans and counter wrap. GPIO calls are substituted; this is an offline model comparison, not a hardware trace or independent ISA proof.
- All 64 six-button bit combinations and explicit press/bounce/release cases pass.
- Host tests cover subscription, deduplication, queued press/release after send failures, overflow, reconnect and sequence wrap.
- Linked Q32S P-code tests exercise the actual patched task call and lifecycle hooks, checking preserved registers, stack/argument layout, original-handler execution and startup clearing. Stock service bodies are substituted; this is not full CPU or device emulation.
- Simulated flash tests inject a failure at each of 112 programmed pages and recover stock each time, preserving all other sectors. Hardware recovery remains untested.
- The independent upstream unpacker extracts the exact custom app and unchanged config, P11, bootloader and chip configuration. See [extraction evidence](evidence/custom-extraction.json).
- The Swift decoder passes all 64 button combinations, overflow and malformed-packet checks; the BLE listener compiles.
- ELF checks enforce the expected target application/call bytes, Q32S machine, entry address, no remaining relocation sections, no extra allocated sections and byte-for-byte text extraction.
- Five existing vendor protocol/address regression tests pass.

## Remaining hardware and integration work

1. Both defects are fixed and audited offline. Application-independent recovery is still not demonstrated; the second unit proceeds only after its stock baseline is physically confirmed. Follow [the failure prevention plan](boot-failure.md).
2. Verify boot, normal HID, all six AE42 button/release states, queue behavior, unsubscribe/resubscribe and reconnect. Check each controller mode and standby/wake.
3. Verify stock restore on hardware. VM, BTIF and USERIF are preserved from two matching reads. Unexpected changes outside these regions and the seven recovery sectors cause refusal; inspect the saved full read instead of bypassing its guard.
4. Add the native Glassly driver and validate iPhone foreground, background, locked-screen and state-restoration behavior.

The older files under `research/candidate/` remain unsuitable for this device layout. The withdrawn image is kept as `research/custom-prepared/custom-device-layout-withdrawn-20261025.bin` for analysis only; per-unit candidates live under `research/custom-prepared/<unit>/`.
