# Q32S decoder and compiler

2026-10-23. The isolated SLEIGH description now decodes all 85 instruction addresses that previously produced constructor failures. Instruction lengths agree with the official disassembler at those sites. This is a bounded regression result, not coverage of every instruction or proof that all generated C is correct. See [audit](evidence/q32s-decoder-audit.json) and [baseline](evidence/q32s-decoder-baseline.json).

## Decoder changes

`research/prepare-q32s.py` copies the pinned processor sources without modifying upstream. It fixes `jls`/`jge` comparisons and 25-bit branch destinations. `research/extend-q32s.py` adds:

- GPR register-list and special-register push/pop semantics.
- 32-bit immediate/register shifts and count-leading-zero.
- Expanded-immediate conditional branches.
- Signed bit-field extraction.
- Zero extension for unsigned immediate comparisons.

Stack frame sizes and calling conventions were checked using compiler-generated C in `research/q32s-compiler-corpus.c`. Register save ordering follows the related PI32V2 module; it has not been verified by a hardware register trace. The GPIO scanner's simulated execution does not exercise these stack operations.

The latest Ghidra pass has no constructor failures in the visited functions, but other P-code errors remain at 42 distinct addresses. ROM bodies are absent, function discovery is heuristic, and some flow/type recovery is incomplete. Condition flags, uncommon instruction families and zero-encoded shift/field widths in existing constructors still need auditing. Generated C retains stack/type warnings and cannot rebuild the original firmware.

## Official compiler

The [Jieli tool download page](https://doc.zh-jieli.com/Tools/zh-cn/other_info/index.html) provides the Linux toolchain. Local archive:

```text
.tools/jieli/toolchain.tar.xz
https://jl-update.oss-cn-shenzhen.aliyuncs.com/jieli-linux-toolchains-20260730.1.tar.xz
SHA256 a1545cddbc451a06bac43eb5cd96d831470c42a97c5c0b1f98879a20fc7647bd
```

Extract it under `.tools/jieli/`. The wrapper expects `.tools/jieli/jieli-linux-toolchains-20260730.1/`. Compiler, linker, disassembler and objcopy were exercised successfully on this Apple Silicon Mac using Linux AMD64 Docker emulation. `scripts/q32s-tool.sh` pins the Debian image, disables container networking and capabilities, mounts source/toolchain read-only, and permits output only under `research/q32s-analysis`.

Example:

```sh
./scripts/q32s-tool.sh clang -target q32s -integrated-as -Os -c research/q32s-compiler-corpus.c -o research/q32s-analysis/compiler-corpus.o
./scripts/q32s-tool.sh objdump -disassemble research/q32s-analysis/compiler-corpus.o
./scripts/build-payload.sh
```

## Reproduce analysis

With the pinned Ghidra installation and Mac decompiler described in [q32s.md](q32s.md):

```sh
./scripts/analyze-q32s.sh
.venv/bin/python research/wrap-stock-elf.py
./scripts/q32s-tool.sh objdump -disassemble -address-mask=0x1ffffff research/q32s-analysis/stock.analysis.elf > research/q32s-analysis/vendor-stock.asm
.venv/bin/python research/audit-q32s-decoder.py
```

The ELF wrapper maps the application and relocated RAM code for analysis only. The linear vendor listing also interprets data as instructions; use it as an opcode reference at known code boundaries. It is not a flash image. Latest Ghidra exports are under `research/q32s-analysis/corrected/`; project names include the run timestamp.

The custom component and recovered scanner are described in [custom-firmware.md](custom-firmware.md).

## Boot audit limits

The original bounded P-code tests did not enforce hardware execution limits and missed an incoming branch to an overwritten epilogue. Both defects were found after the October 25 hardware failure. `test_boot_audit.py` now derives limits from the actual boot instructions, checks protected custom fetches and exercises unchanged BLE states. Only its protected model enables the optional fetch hook; the general interpreter remains a subset model without full MMIO, alignment, interrupts or boot emulation. See [failure analysis](boot-failure.md).
