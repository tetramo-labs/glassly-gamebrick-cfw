#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p research/q32s-analysis
swiftc -module-cache-path research/q32s-analysis/swift-cache probes/GamebrickPacket.swift probes/GamebrickCapture.swift research/test-gamebrick-capture.swift -o research/q32s-analysis/test-gamebrick-capture
research/q32s-analysis/test-gamebrick-capture
swiftc -module-cache-path research/q32s-analysis/swift-cache probes/GamebrickPacket.swift probes/GamebrickCapture.swift probes/gamebrick-vendor.swift -o research/q32s-analysis/gamebrick-vendor
