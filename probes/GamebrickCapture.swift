import Foundation

/// Session evidence; input coverage requires isolated presses followed by release.
struct GamebrickCapture {
    private(set) var packets = 0
    private(set) var invalidPackets = 0
    private(set) var gaps = 0
    private(set) var overflows = 0
    private(set) var pressedMask: UInt8 = 0
    private(set) var releasedMask: UInt8 = 0
    private(set) var held: UInt8 = 0
    private(set) var lastSequence: UInt8?
    private var isolatedPress: UInt8 = 0

    mutating func resetConnection() {
        held = 0
        lastSequence = nil
        isolatedPress = 0
    }

    mutating func accept(_ data: Data) -> [String: Any] {
        guard let packet = GamebrickPacket(data) else {
            invalidPackets += 1
            return ["event": "unrecognized", "hex": data.map { String(format: "%02x", $0) }.joined()]
        }
        let isBaseline = lastSequence == nil
        let gap = lastSequence.map { packet.sequence != ($0 &+ 1) } ?? false
        if gap {
            gaps += 1
        }
        if packet.overflow {
            overflows += 1
        }
        let pressed: UInt8 = isBaseline ? 0 : packet.buttons & ~held
        let released: UInt8 = isBaseline ? 0 : held & ~packet.buttons
        if gap || packet.overflow {
            isolatedPress = 0
        }
        // A first/reconnected snapshot is state, not proof of a physical press.
        if !isBaseline, !gap, !packet.overflow {
            if held == 0, packet.buttons.nonzeroBitCount == 1 {
                isolatedPress = packet.buttons
                pressedMask |= packet.buttons
            } else if packet.buttons == 0, held == isolatedPress {
                releasedMask |= isolatedPress
                isolatedPress = 0
            } else if packet.buttons != held {
                isolatedPress = 0
            }
        }
        packets += 1
        lastSequence = packet.sequence
        held = packet.buttons
        return ["event": "buttons", "sequence": Int(packet.sequence), "buttons": Int(packet.buttons),
                "held": GamebrickPacket.names(packet.buttons), "pressed": GamebrickPacket.names(pressed),
                "released": GamebrickPacket.names(released), "baseline": isBaseline,
                "overflow": packet.overflow, "sequence_gap": gap]
    }

    var summary: [String: Any] {
        ["event": "summary", "packets": packets, "unrecognized": invalidPackets,
         "sequence_gaps": gaps, "overflows": overflows,
         "isolated_pressed_mask": Int(pressedMask), "isolated_released_mask": Int(releasedMask),
         "all_six_press_release_observed": pressedMask == 63 && releasedMask == 63,
         "final_buttons": lastSequence == nil ? NSNull() : Int(held) as Any, "ios_background_verified": false]
    }
}
