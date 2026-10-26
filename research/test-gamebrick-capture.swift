import Foundation

@main
struct CaptureTests {
    static func main() {
        var capture = GamebrickCapture()
        var sequence: UInt8 = 255
        func packet(_ buttons: UInt8) -> Data {
            defer { sequence &+= 1 }
            return Data([0x47, 1, sequence, buttons])
        }
        _ = capture.accept(packet(0))
        for bit in 0 ..< 6 {
            _ = capture.accept(packet(1 << bit))
            _ = capture.accept(packet(0))
        }
        assert(capture.pressedMask == 63 && capture.releasedMask == 63 && capture.gaps == 0)
        capture.resetConnection()
        let baseline = capture.accept(packet(1))
        assert(baseline["baseline"] as? Bool == true)
        assert(baseline["pressed"] as? String == "none" && baseline["released"] as? String == "none")
        var reconnect = GamebrickCapture()
        _ = reconnect.accept(packet(1))
        _ = reconnect.accept(packet(0))
        assert(reconnect.pressedMask == 0 && reconnect.releasedMask == 0)
        _ = reconnect.accept(packet(2))
        reconnect.resetConnection()
        _ = reconnect.accept(packet(0))
        assert(reconnect.releasedMask == 0)
        _ = reconnect.accept(packet(2))
        sequence &+= 1
        _ = reconnect.accept(packet(0))
        assert(reconnect.gaps == 1 && reconnect.releasedMask == 0)
        _ = reconnect.accept(packet(2))
        _ = reconnect.accept(packet(0x40))
        assert(reconnect.overflows == 1 && reconnect.releasedMask == 0)
        _ = reconnect.accept(Data([0xB4, 1, 0, 0]))
        assert(reconnect.invalidPackets == 1)
        print("PASS: isolated button coverage, wrap, reconnect baseline, gaps, overflow and malformed data")
    }
}
