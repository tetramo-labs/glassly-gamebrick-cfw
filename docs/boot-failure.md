# Custom firmware boot failure

2026-10-25. Two defects are confirmed in the application extracted from the saved flashed target (`bec28bd2…`). The execution-limit violation is the strongest explanation for the reported reset loop. No live exception trace was captured, so the first failing instruction remains unconfirmed. The failed candidate is withdrawn. A replacement candidate that fixes both defects was built on 2026-10-28; see [the fix](#replacement-candidate-2026-10-28).

## Execution outside the permitted code range

Stock startup calls `debug_init` at `0x01e10a5a`. Its actual instructions set `EMU_CON` (`0x001be200`) to `0x80000017`, enabling PC-limit protection, and configure these ranges:

| Region | Lower limit | Upper limit |
| --- | --- | --- |
| Flash text | `0x01e00120` | `0x01e2dfc8` |
| RAM code | `0x000040c0` | `0x000061a8` |
| ROM | `0x00100000` | `0x00110000` |

The appended 376-byte payload occupies `0x01e309d0..0x01e30b47`, outside every range. Appending after the application file also put it after the initialized RAM data/code image, beyond the original linked text. All four custom destinations are outside the configured limits. Entering them should raise an execution exception.

The BD19 SDK at commit `fdc018de81629e21e594d677cf05f87d288be0f0` corroborates the register identities and initialization: `include_lib/driver/cpu/bd19/asm/csfr.h` and the `debug.c.o` member of `cpu/bd19/liba/cpu.a`. That member is LLVM bitcode; its decoded `debug_init` writes the same control value and uses the linked `text_begin/text_end` and RAM-code limits. Local IR: `research/q32s-analysis/sdk-debug.ll`.

The actual firmware's RAM exception stub at `0x5e20` calls `0x01e0f898`. This handler stores marker `0xab` at `0x1a184a`, then jumps to the reset routine at `0x42e8`, which sets bits `0x30` at `0x1a18a0`. The SDK names the corresponding path `exception_analyze_release` / `p33_soft_reset`; startup recognizes the marker as `soft_reset_exception`. This supplies a concrete exception-to-reset path. It has not been observed live on this controller.

## Branch into the middle of a patched instruction

The BLE state setter at `0x01e05248` skips its event call when the requested state already equals the current state. Its branch at `0x01e05256` targets the original epilogue at `0x01e05276`.

| Address | Stock | Failed patch |
| --- | --- | --- |
| `0x01e05274` | Two-byte call | Start of four-byte jump |
| `0x01e05276` | Restore registers and return | Second half of that jump |

The unchanged-state branch was left intact. At its target the new bytes `bd 5b` decode as `h[r5 + 0x36] = r5`: an unintended write into low RAM, followed by fallthrough into the next function without restoring the saved stack frame. Tests reproduce this for states 0, 1 and 7; stock returns normally for the same inputs. Odd addresses may fault on hardware earlier than the model, which does not enforce alignment.

Widening the PC range alone leaves this defect. Restoring the original epilogue alone leaves the execution-limit defect. Neither is a complete fix.

## What the three blinks establish

The repeated white three-blink sequence and unresponsive controls are consistent with recurring startup/reset. They do not identify a particular exception. No dedicated three-blink fault code was found in the reviewed firmware paths or the [official IINE guide](https://iine.store/pages/gamebrick-mini-retro-controller-guide-manual). The guide uses white for T mode, red for C and yellow for H. The recovered LED logic also uses white in normal T-mode operation; that does not explain the exact reported cadence.

The reviewed low-battery path uses five red flashes, which does not match the report. UART exception/reset output or an observed reset signal is still needed to confirm the live reset cause. A flash readback match establishes the bytes written, not successful boot.

## Checks added

`research/boot_audit.py` executes the actual debug-register setup in the bounded P-code model, checks all four hook destinations and appended instruction addresses against those limits, and checks branch targets against instruction boundaries across the affected BLE function. Disabling PC protection is rejected. This is an exact-version audit, not a general verifier or complete CPU emulator.

`flash_custom.py check` and `install` now reject this candidate before opening USB or creating an operation directory. `restore` remains available with the existing identity, storage-preservation and readback guards. The failed firmware bytes and hashes are unchanged for reproducibility and restoration.

Eight regression tests cover the captured failed application, stock acceptance, all custom entries with protected fetches, unchanged BLE states, independent isolation of both defects, disabled protection, rejection before USB, and simulated restoration of the actual captured target to its saved stock image. The old tests omitted execution protection and exercised only the changed-state lifecycle path.

```sh
.venv/bin/python research/test_boot_audit.py -v
.venv/bin/python research/boot_audit.py
```

The first command passes; the second must exit 1 for the failed candidate. `scripts/check-custom.sh` includes the regression tests and must fail at its final installability check until a replacement has been reviewed. Historical passing model tests do not override this gate.

## Replacement candidate: 2026-10-28

Both defects are fixed at their cause, and the offline audit now rejects either regression. Nothing has been flashed.

**Execution limit.** The payload remains appended after the application image, because the linked text is immediately followed by the initialized RAM data and RAM code images and has no free space. `debug_init` programs the flash text upper limit from the immediate at `0x01e10a90`. The packager now rewrites that one immediate to exactly the new application end (`0x01e30b60` for the current payload), so placement and protection bound change together. Protection stays enabled, the lower limit and the RAM/ROM ranges stay stock, and the startup data-copy source at `0x01e00174`, which uses the same constant, is untouched. The audit executes the actual `debug_init` and reports `FLASH_TEXT_LIMIT_MISMATCH` if the limit differs from the application end by even one byte in either direction, `EXECUTION_LIMITS_CHANGED` if any other range moves, and `STARTUP_DATA_COPY_CHANGED` if the copy source changes.

**BLE epilogue.** The hook moved four bytes earlier, onto the two register moves `r1 = r5; r2 = r4` at `0x01e05270`, which the wrapper now performs itself before calling the event wrapper and popping the original frame. The stock two-byte call at `0x01e05274` and the epilogue at `0x01e05276` are preserved byte for byte, so the unchanged-state branch at `0x01e05256` still lands on an intact return. The P-code regressions execute states 0, 1 and 7 unchanged on both stock and candidate: RAM, stack and epoch are untouched and no event is sent. A changed state sends the event once and advances the epoch once.

Tests: `research/test_boot_audit.py` (12 tests) covers the withdrawn image, the candidate under protected fetch at all hook sites, limit tampering in both directions, and restore of the actual unit1 target. `./scripts/check-custom.sh` runs everything for the current unit and the unit1 history.

## Before another device receives custom firmware

1. Establish a working stock baseline and demonstrate recovery that does not depend on the application running, using the identified board and boot-ROM procedure.
2. Place code in a verified executable region, or explicitly revise the linked code layout and protection bounds together. Do not disable protection. Audit RAM, flash, stack and initialization overlap.
3. Preserve all incoming branches, returns and instruction boundaries at every patched site. Exercise changed and unchanged states, startup, reconnect, unsubscribe and standby/wake paths.
4. Review the new image and hashes independently from this failed candidate. Add bounded startup/protection checks and a staged hardware test with reset diagnostics and proven recovery available.
5. Verify boot, all physical controls, normal HID and recovery before testing AE42 and iOS background delivery.

The new checks prevent these known defects from passing the current installer. They do not establish that the replacement image boots. Step 1's application-independent recovery remains undemonstrated; the user accepted that risk for the second unit after the stock baseline is confirmed.

Machine-readable evidence: [boot-failure.json](evidence/boot-failure.json). Hardware recovery remains pending: [recovery.md](recovery.md).
