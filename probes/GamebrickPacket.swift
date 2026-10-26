import Foundation

struct GamebrickPacket: Equatable {
    let sequence: UInt8
    let buttons: UInt8
    let overflow: Bool

    init?(_ data: Data) {
        let bytes = Array(data)
        guard bytes.count == 4, bytes[0] == 0x47, bytes[1] == 1, bytes[3] & 0x80 == 0 else {
            return nil
        }
        sequence = bytes[2]
        buttons = bytes[3] & 0x3F
        overflow = bytes[3] & 0x40 != 0
    }

    static func names(_ mask: UInt8) -> String {
        let labels = ["Up", "Down", "Left", "Right", "A", "B"]
        let active = labels.enumerated().compactMap { index, name in
            mask & (1 << index) != 0 ? name : nil
        }
        return active.isEmpty ? "none" : active.joined(separator: ",")
    }
}
