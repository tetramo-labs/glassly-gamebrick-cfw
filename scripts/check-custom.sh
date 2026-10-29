#!/bin/sh
# Offline checks for the current unit (research/devices.json or GB_DEVICE), plus the
# historical unit1 regressions that reproduce the 2026-10-25 boot failure.
set -eu
cd "$(dirname "$0")/.."
unit=$(.venv/bin/python research/device_profile.py)
echo "Current unit: $unit"
./scripts/build-payload.sh
.venv/bin/python research/stock_update.py
.venv/bin/python research/custom_image.py
.venv/bin/python research/boot_audit.py > "research/custom-prepared/$unit/boot-audit.json"
.venv/bin/python research/test_payload_q32s.py -v
.venv/bin/python research/test_custom_image.py -v
.venv/bin/python research/test_custom_runtime.py -v
.venv/bin/python research/test_stock_protocol.py -v
.venv/bin/python research/test_stock_update.py
.venv/bin/python research/test_flasher.py -v
.venv/bin/python research/test_usb_transport.py -v
.venv/bin/python scripts/verify-backup.py
.venv/bin/python research/jl-misctools/firmware/fwunpack_newfw.py --dirname "research/custom-prepared/$unit/independent-unpack" "research/custom-prepared/$unit/custom-device-layout.bin" > "research/custom-prepared/$unit/unpack.log" 2>&1
.venv/bin/python research/verify-custom-extraction.py
echo "Historical unit1 regressions"
GB_DEVICE=unit1 .venv/bin/python research/custom_image.py
GB_DEVICE=unit1 .venv/bin/python research/test_boot_audit.py -v
GB_DEVICE=unit1 .venv/bin/python research/test_custom_baseline.py -v
GB_DEVICE=unit1 .venv/bin/python research/test_custom_runtime.py -v
swiftc -module-cache-path research/q32s-analysis/swift-cache probes/GamebrickPacket.swift research/test-gamebrick-packet.swift -o research/q32s-analysis/test-gamebrick-packet
research/q32s-analysis/test-gamebrick-packet
cp probes/gamebrick-listen.swift research/q32s-analysis/main.swift
swiftc -module-cache-path research/q32s-analysis/swift-cache probes/GamebrickPacket.swift research/q32s-analysis/main.swift -o research/q32s-analysis/gamebrick-listen
.venv/bin/python research/flash_custom.py check

./scripts/build-vendor-probe.sh
