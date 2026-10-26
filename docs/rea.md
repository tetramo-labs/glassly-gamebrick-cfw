# REA investigation

REA source is downloaded in `research/rea/`, pinned in `sources.lock.json` to `e073f64be0a5a30c32d8b3cec23f9bd411080903`. CLI release **6.7.0** is installed locally in `.tools/rea/`. Commands use the existing Node **26.8.2** installation; the shell's default Node 22.15.0 does not satisfy REA's runtime requirement.

The [REA skill](https://github.com/morluto/rea/blob/e073f64be0a5a30c32d8b3cec23f9bd411080903/.agents/skills/reverse-engineer-anything/SKILL.md) was read and applied. CLI use does not register an MCP server or modify agent configuration. No analysis engine was installed.

## Commands executed

```sh
./scripts/rea.sh --version
./scripts/rea.sh inspect-artifact research/stock-update.zip --format json
./scripts/rea.sh inspect-artifact research/device-backup-20261022-233350/unpacked/files/app.bin --format json
./scripts/rea.sh doctor --client codex --format json
```

Complete outputs are preserved locally in `research/rea-output/`. The package evidence and unsupported-target result are also copied to `docs/evidence/` for version control. Doctor output stays local because it inventories host paths and configuration.

## Results

- OEM package inspection succeeded. REA verified the ZIP digest and inventoried the firmware UFW, Windows PE updater and instruction document. The graph has five nodes including the root and enclosing directory. This establishes package membership and hashes, not firmware behavior or authenticity.
- Installed `app.bin` inspection returned `target_unavailable`, category `unsupported_target`, reason `unsupported binary format`. No Q32S disassembly or decompilation was produced by REA.
- The [raw-binary guide](https://github.com/morluto/rea/blob/e073f64be0a5a30c32d8b3cec23f9bd411080903/docs/raw-binary.md) and installed CLI admit x86, x86_64, ARM, AArch64, 6502 and m68k. Q32S is absent. Do not label the input as ARM to bypass admission.
- Doctor found no configured Hopper, Ghidra or IDA engine and no aligned Codex REA registration. Those are additional limits for native analysis, not problems for the completed ZIP inventory. Installing Ghidra alone would not add Q32S to REA's raw-target admission.
- REA's firmware-region workflow requires Linux and caller-supplied Binwalk/Unblob. It was not run on this Mac.

## Continue

Use `./scripts/rea.sh` for supported artifact inspection. `./scripts/setup-rea.sh` reinstalls the same release without changing agent configuration. Set `REA_NODE` to a supported Node executable on another machine.

Continue Q32S analysis with the preserved Jieli SLEIGH definitions and pypcode tools, or explicitly scope a Q32S extension to REA before depending on it. All existing function and patch findings came from the Jieli tools and local analysis, not REA.

The npm install reported an unapproved optional Frida install script. No Frida runtime or injection workflow was used or validated; the static CLI commands above worked without it.
