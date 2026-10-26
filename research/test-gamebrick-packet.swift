import Foundation

@main
struct PacketTests {
    static func main() {
        for value in UInt8(0) ..< 64 {
            let packet = GamebrickPacket(Data([0x47, 1, 255, value]))!
            assert(packet.buttons == value && packet.sequence == 255 && !packet.overflow)
        }
        let overflow = GamebrickPacket(Data([0x47, 1, 0, 0x7F]))!
        assert(overflow.buttons == 63 && overflow.overflow)
        assert(GamebrickPacket.names(63) == "Up,Down,Left,Right,A,B")
        assert(GamebrickPacket.names(0) == "none")
        for data in [[UInt8](), [0x47, 1, 0], [0x47, 1, 0, 0, 0], [0xB4, 1, 0, 0], [0x47, 2, 0, 0], [0x47, 1, 0, 0x80]] {
            assert(GamebrickPacket(Data(data)) == nil)
        }
        print("PASS: six-button packet decoding, overflow, labels and malformed packets")
    }
}
