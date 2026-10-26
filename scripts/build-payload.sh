#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p research/q32s-analysis
./scripts/q32s-tool.sh clang -target q32s -integrated-as -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -Os -Wall -Wextra -Werror -c firmware/input_state.c -o research/q32s-analysis/input_state.o
./scripts/q32s-tool.sh clang -target q32s -integrated-as -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -Os -Wall -Wextra -Werror -c firmware/vendor_stream.c -o research/q32s-analysis/vendor_stream.o
./scripts/q32s-tool.sh clang -target q32s -integrated-as -c firmware/task_hooks.S -o research/q32s-analysis/task_hooks.o
./scripts/q32s-tool.sh ld --gc-sections -T firmware/payload.ld research/q32s-analysis/input_state.o research/q32s-analysis/vendor_stream.o research/q32s-analysis/task_hooks.o -o research/q32s-analysis/vendor-payload.elf
./scripts/q32s-tool.sh objdump -disassemble research/q32s-analysis/vendor-payload.elf > research/q32s-analysis/vendor-payload.asm
./scripts/q32s-tool.sh objcopy -j .text -O binary research/q32s-analysis/vendor-payload.elf research/q32s-analysis/vendor-payload.bin
clang -Wall -Wextra -Werror -DGB_HOST_TEST firmware/input_state.c firmware/vendor_stream.c research/test_vendor_stream.c -o research/q32s-analysis/test_vendor_stream
research/q32s-analysis/test_vendor_stream
clang -Wall -Wextra -Werror -dynamiclib firmware/input_state.c -o research/q32s-analysis/libinput_state.dylib
.venv/bin/python research/test_input_state.py -v

.venv/bin/python research/verify-payload.py
