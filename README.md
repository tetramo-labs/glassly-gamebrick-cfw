# Glassly firmware for the IINE Gamebrick Mini

Custom firmware for the [IINE Gamebrick Mini Retro Controller](https://iine.store/products/iine-gamebrick-mini-retro-controller) (L1161/L1162) that streams its six buttons to the Glassly App over a Bluetooth LE vendor characteristic, so the controller works as a Glassly controller on iOS and Android, including in the background. The stock firmware is a plain HID gamepad, which phone apps cannot read.

Everything the stock controller does is kept. The patch adds one notification stream (service `AE40`, characteristic `AE42`) next to the official firmware's own features and modes.

## Flash your Gamebrick

You need a computer running macOS, Windows or Linux, the controller's USB-C **data** cable, and about ten minutes. The controller can only be flashed over USB: it has no over-the-air update path a phone could use. The Glassly application and IINE's official one are included in this repository and hash-checked on every run; nothing is downloaded.

The flasher has been run on macOS. The Windows and Linux paths use the operating system's own SCSI pass-through, the same mechanism the upstream Jieli tooling uses, but have not yet been exercised on a controller. If you try one, please open an issue with the result either way.

### macOS

1. Install the Xcode Command Line Tools if you have not: `xcode-select --install`.
2. Get the tool and set it up (fetches two small pinned helper repositories and builds the USB transport):

   ```sh
   git clone https://github.com/tetramo-labs/glassly-gamebrick-cfw.git
   cd glassly-gamebrick-cfw
   ./scripts/setup.sh
   ```

3. Start the flasher from your own terminal. It needs `sudo` for USB access, and macOS asks for permission to access removable volumes the first time:

   ```sh
   sudo .venv/bin/python -u research/flash_gamebrick.py install
   ```

4. Put the controller in update mode when the flasher asks: with it **switched on and plugged in**, hold **Pairing + B** for about two seconds until the light goes out, then release. The flasher takes it from there and ends with `FLASH VERIFIED`.
5. Unplug, power-cycle, and pair it in the Glassly App under Controllers. Any mode works (T, C or H).

### Windows

1. Install [Python 3](https://www.python.org/downloads/windows/) (tick "Add python.exe to PATH") and [Git for Windows](https://git-scm.com/download/win). No driver is needed: in update mode the controller is a plain USB disk.
2. Open **Terminal** or **PowerShell as Administrator** (the flasher talks to the controller through raw disk access, which Windows only allows to administrators), then:

   ```powershell
   git clone https://github.com/tetramo-labs/glassly-gamebrick-cfw.git
   cd glassly-gamebrick-cfw
   python scripts\setup.py
   ```

3. In the same Administrator window:

   ```powershell
   .venv\Scripts\python -u research\flash_gamebrick.py install
   ```

4. Put the controller in update mode when the flasher asks: with it **switched on and plugged in**, hold **Pairing + B** for about two seconds until the light goes out, then release. If Windows offers to format the new drive, close that dialog; the flasher does not need it. It ends with `FLASH VERIFIED`.
5. Unplug, power-cycle, and pair it in the Glassly App under Controllers.

### Linux

1. Install Python 3 and Git from your distribution. The flasher uses the kernel's SCSI generic devices (`/dev/sg*`), which every mainstream kernel has.
2. Set up:

   ```sh
   git clone https://github.com/tetramo-labs/glassly-gamebrick-cfw.git
   cd glassly-gamebrick-cfw
   ./scripts/setup.sh
   ```

3. Start the flasher with `sudo` (or as a user in the `disk` group):

   ```sh
   sudo .venv/bin/python -u research/flash_gamebrick.py install
   ```

4. Put the controller in update mode when the flasher asks: with it **switched on and plugged in**, hold **Pairing + B** for about two seconds until the light goes out, then release. If your desktop auto-mounts the new disk, unmount it first; a mounted drive can hold the device busy. It ends with `FLASH VERIFIED`.
5. Unplug, power-cycle, and pair it in the Glassly App under Controllers.

If the controller was never updated by IINE's Windows tool, this installs the current official application and the Glassly patch in one pass. If it already runs the official update, only eight sectors change. Running it again on a flashed controller does nothing.

### What the flasher does and never does

- Reads the entire flash twice, keeps both reads as a backup next to the log (`research/gamebrick-install-*/`), and refuses to continue unless the contents match one of the three known images (factory, official update, Glassly) outside the controller's own storage.
- Builds the new image from the controller's own flash and the committed, hash-pinned applications. Bluetooth pairing data, settings and the key/MAC sector are never written.
- Writes only the application area, commits the header sector last, and verifies every byte of the flash afterwards.
- Never erases the whole chip, never touches fuses or chip keys, and never sends a command outside its allowlist.

### Going back to the official firmware

Run the same command with `restore` instead of `install` (on Windows, `.venv\Scripts\python -u research\flash_gamebrick.py restore` from an Administrator window). Same update-mode dance; this puts the official IINE application back. `backup` reads the flash without writing anything.

### Buttons in Glassly

| Button | Gesture |
| --- | --- |
| D-pad | `swipe_up`, `swipe_down`, `swipe_left`, `swipe_right`, one per press |
| A | `touch_down` on press, `tap_start` once held 400 ms, `tap_end` on release, `single_tap` after a quick press |
| B | `double_tap` |

### If something goes wrong

The flasher stops before writing on anything it does not recognise. If it stops after writing, run it again: a verified write is resumable from any of the known states. A controller that does not come back after a verified flash is the one case we cannot recover from a computer yet; see [recovery](docs/recovery.md). The first prototype did exactly that on 2026-10-25, which is why the current image went through the checks described below before it reached a second unit.

## How it works

- [Findings](docs/findings.md): the hardware (Jieli BD19), the recovered input path, the vendor protocol, and the two units flashed so far.
- [Custom firmware](docs/custom-firmware.md): the hooks, the AE42 packet, and the build.
- [Boot failure and fix](docs/boot-failure.md): the two defects of the withdrawn first image and the audit that now rejects them.
- [Install and restore](docs/custom-install.md): the per-unit research workflow with explicit stock and custom steps.
- [Plan](docs/plan.md), [resources](docs/resources.md), [Q32S notes](docs/q32s.md).

The Glassly App side lives in the Glassly repository (`IINE Gamebrick` controller, source 5).
