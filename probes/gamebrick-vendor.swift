import CoreBluetooth
import Foundation

private func emit(_ event: [String: Any]) {
    var row = event
    row["time"] = ISO8601DateFormatter().string(from: Date())
    if let data = try? JSONSerialization.data(withJSONObject: row, options: [.sortedKeys]),
       let line = String(data: data, encoding: .utf8)
    {
        print(line)
        fflush(stdout)
    }
}

final class VendorProbe: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    private let service = CBUUID(string: "AE40")
    private let notify = CBUUID(string: "AE42")
    private var central: CBCentralManager!
    private var target: CBPeripheral?
    private var capture = GamebrickCapture()
    private var seen = Set<UUID>()
    private var finished = false
    private let identifier: UUID?

    init(identifier: UUID?, duration: Int) {
        self.identifier = identifier
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
        DispatchQueue.main.asyncAfter(deadline: .now() + .seconds(duration)) { self.finish() }
    }

    private func finish() {
        guard !finished else { return }
        finished = true
        central.stopScan()
        if let target {
            central.cancelPeripheralConnection(target)
        }
        emit(capture.summary)
        exit(0)
    }

    private func connect(_ peripheral: CBPeripheral) {
        guard !finished, target == nil else { return }
        target = peripheral
        central.stopScan()
        peripheral.delegate = self
        emit(["event": "connecting", "id": peripheral.identifier.uuidString, "name": peripheral.name ?? ""])
        central.connect(peripheral)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        emit(["event": "bluetooth", "state": central.state.rawValue, "authorization": CBManager.authorization.rawValue])
        guard central.state == .poweredOn else { return }
        if let identifier, let peripheral = central.retrievePeripherals(withIdentifiers: [identifier]).first {
            connect(peripheral)
        } else {
            let connected = central.retrieveConnectedPeripherals(withServices: [service])
            for peripheral in connected {
                emit(["event": "already_connected", "id": peripheral.identifier.uuidString,
                      "name": peripheral.name ?? "", "service": "AE40"])
            }
            let matches = connected.filter { peripheral in
                if let identifier {
                    return peripheral.identifier == identifier
                }
                let name = peripheral.name?.lowercased() ?? ""
                return name.contains("iine") || name.contains("gamebrick") || name == "xbox wireless controller"
            }
            if matches.count == 1 {
                connect(matches[0])
            } else {
                // Foreground discovery: the stock advertisement may omit AE40.
                central.scanForPeripherals(withServices: nil, options: nil)
            }
        }
    }

    func centralManager(_: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber)
    {
        let name = advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? peripheral.name ?? ""
        let manufacturer = advertisementData[CBAdvertisementDataManufacturerDataKey] as? Data ?? Data()
        let match = identifier.map { peripheral.identifier == $0 } ??
            (name.lowercased().contains("iine") || name.lowercased().contains("gamebrick") ||
                manufacturer.range(of: Data("mt_IINE".utf8)) != nil)
        guard match else { return }
        if seen.insert(peripheral.identifier).inserted {
            let services = advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID] ?? []
            emit(["event": "advertisement", "id": peripheral.identifier.uuidString, "name": name,
                  "rssi": RSSI.intValue, "services": services.map(\.uuidString),
                  "manufacturer": manufacturer.map { String(format: "%02x", $0) }.joined()])
        }
        connect(peripheral)
    }

    func centralManager(_: CBCentralManager, didConnect peripheral: CBPeripheral) {
        capture.resetConnection()
        emit(["event": "connected", "id": peripheral.identifier.uuidString])
        peripheral.discoverServices([service])
    }

    func centralManager(_: CBCentralManager, didFailToConnect _: CBPeripheral, error: Error?) {
        emit(["event": "connect_failed", "error": error?.localizedDescription ?? "unknown"])
        finish()
    }

    func centralManager(_: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        emit(["event": "disconnected", "error": error?.localizedDescription ?? ""])
        capture.resetConnection()
        // Do not invent releases when a connection disappears; record the loss.
        guard !finished else { return }
        target = nil
        connect(peripheral)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil, let found = peripheral.services?.first(where: { $0.uuid == service }) else {
            emit(["event": "service_missing", "error": error?.localizedDescription ?? "AE40 absent"])
            finish(); return
        }
        peripheral.discoverCharacteristics([notify], for: found)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil, let characteristic = service.characteristics?.first(where: { $0.uuid == notify }),
              characteristic.properties.contains(.notify)
        else {
            emit(["event": "characteristic_missing", "error": error?.localizedDescription ?? "AE42 notify absent"])
            finish(); return
        }
        peripheral.setNotifyValue(true, for: characteristic)
    }

    func peripheral(_: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        emit(["event": "subscription", "uuid": characteristic.uuid.uuidString,
              "enabled": characteristic.isNotifying, "error": error?.localizedDescription ?? ""])
        if error != nil {
            finish()
        }
    }

    func peripheral(_: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard characteristic.uuid == notify else { return }
        if let error {
            emit(["event": "notify_error", "error": error.localizedDescription]); return
        }
        emit(capture.accept(characteristic.value ?? Data()))
    }
}

@main
struct VendorMain {
    static func main() {
        let args = Array(CommandLine.arguments.dropFirst())
        guard args.count <= 2, let duration = args.first.flatMap(Int.init) ?? (args.isEmpty ? 150 : nil),
              (1 ... 600).contains(duration), args.count < 2 || UUID(uuidString: args[1]) != nil
        else {
            fputs("Usage: gamebrick-vendor [seconds:1..600] [peripheral-UUID]\n", stderr)
            exit(2)
        }
        emit(["event": "start", "duration": duration, "subscription": "AE42 only", "gamecontroller_api": false])
        let probe = VendorProbe(identifier: args.count == 2 ? UUID(uuidString: args[1]) : nil, duration: duration)
        withExtendedLifetime(probe) { RunLoop.main.run() }
    }
}
