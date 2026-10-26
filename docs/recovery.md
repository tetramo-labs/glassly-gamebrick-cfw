# Recovery after custom firmware startup failure

2026-10-25. Recovery is not yet completed.

## Observed

- The custom image was written and fully verified: `bec28bd21195de6d5ef50a0fb163a5dd8d669aeba2aa38e79b8ca37a2cc2073b`.
- The user reports endless groups of three white blinks and no response to controls, then reports being unable to enter update mode.
- BLE scans found no matching controller. A roughly ten-second USB enumeration poll found neither normal gamepad nor update mode. Cable connection during that poll was not confirmed.
- A reset loop is suspected, not established by a reset-cause register or debug trace. No further flash writes have been attempted by the agent.

## Why the current writer cannot recover it yet

`flash_custom.py restore` waits for the existing USB bootloader interface (`4c4a:3442`). It does not force entry into boot ROM. If Pairing+B is processed by the application and the application resets first, shortening the host polling interval will not fix entry. This explanation is a hypothesis for this device, not a traced button-handler result.

The bootloader and key/MAC sector were not changed by the custom install. The full factory backup and the pre-custom official stock image remain available. That preserves recovery material; it does not prove a hardware recovery interface is accessible.

## Documented hardware routes

Jieli's forced-upgrade tool sends a handshake at chip reset, before application execution. Its official AC63 hardware guide uses the Jieli forced-upgrade tool 4.0 with an AC6321A development board. This supports investigating a compatible Jieli tool for BD19/AC632N; Gamebrick PCB wiring, reset/power control and adapter compatibility still need confirmation.

- [Jieli forced-upgrade operation](https://doc.zh-jieli.com/Tools/zh-cn/dev_tools/forced_upgrade/upgrade_and_download.html): reset plus USB/ISP/UART key handshake; mode 3 repeats the handshake but still requires a chip reset.
- [AC63 hardware preparation](https://doc.zh-jieli.com/AC63/zh-cn/release_v2.3.0/getting_started/preparation/hardware.html): tool 4.0 and AC6321A development board.
- [Upstream boot-entry research](https://github.com/kagaimiq/jl-uboot-tool/blob/main/docs/how-to-enter-uboot.md): USB_KEY is a signal on D+/D-, followed by handoff to the USB host. It is not an ordinary command the existing Mac writer sends.

A generic USB-UART adapter is not assumed to be sufficient. The local tool has a BD19 UART loader but lists BD19 support as unknown; this repo has only verified its own USB path. Do not treat a debug UART pin as a validated download connection. Do not short flash or guessed test pads based on documentation for another chip/board.

## Next steps

1. Confirm the same USB data cable is connected and identify available programming hardware.
2. Inspect clear photographs of both PCB sides and the exact main-chip marking before specifying wiring. Identify battery connection, USB data routing and any reset/download pads.
3. Confirm voltage, reset/power sequencing and forced-entry method for this board; use the hardware tool only to enter recovery initially, without launching an automatic erase/download job.
4. Once USB bootloader enumeration is stable, use the existing identity-checked restore command from the user's interactive terminal:

```sh
cd ~/dev/glassly-mini-gamepad
sudo .venv/bin/python -u research/flash_custom.py restore
```

The writer verifies BD19 and flash identity, reads twice, saves artifacts, restores only the seven patch sectors, preserves live VM/BTIF/USERIF, and verifies the full result. Stop on any guard failure. Do not install generic SDK firmware or erase the whole flash.

5. Verify stock boot, USB HID and all buttons before investigating the custom fault. Do not reinstall the current custom candidate.
