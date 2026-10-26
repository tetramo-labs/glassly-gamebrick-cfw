import Foundation
import CoreBluetooth

final class Inspector: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    var central: CBCentralManager!
    var target: CBPeripheral?
    var seen = Set<UUID>()
    var pending = 0
    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
    }
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        print("Bluetooth state: \(central.state.rawValue); authorization: \(CBManager.authorization.rawValue)")
        fflush(stdout)
        if central.state == .poweredOn {
            central.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
            print("Scanning BLE advertisements for 25 seconds...")
            fflush(stdout)
        }
    }
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? peripheral.name ?? "(unnamed)"
        if seen.insert(peripheral.identifier).inserted {
            print("Found: \(name) | RSSI \(RSSI) | services \(advertisementData[CBAdvertisementDataServiceUUIDsKey] ?? [])")
            fflush(stdout)
        }
        if target == nil && (name.localizedCaseInsensitiveContains("xbox") || name.localizedCaseInsensitiveContains("iine") || name.localizedCaseInsensitiveContains("gamebrick")) {
            target = peripheral
            peripheral.delegate = self
            print("Inspecting: \(name); advertisement: \(advertisementData)")
            fflush(stdout)
            central.stopScan()
            central.connect(peripheral)
        }
    }
    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        print("Connected; discovering services")
        fflush(stdout)
        peripheral.discoverServices(nil)
    }
    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        print("Connection failed: \(String(describing: error))")
        fflush(stdout)
    }
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        print("Service discovery error: \(String(describing: error))")
        let services = peripheral.services ?? []
        pending = services.count
        for service in services {
            print("Service: \(service.uuid.uuidString)")
            peripheral.discoverCharacteristics(nil, for: service)
        }
        fflush(stdout)
    }
    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        print("Characteristics for \(service.uuid.uuidString); error: \(String(describing: error))")
        for c in service.characteristics ?? [] {
            var flags: [String] = []
            if c.properties.contains(.read) { flags.append("read") }
            if c.properties.contains(.write) { flags.append("write") }
            if c.properties.contains(.writeWithoutResponse) { flags.append("writeWithoutResponse") }
            if c.properties.contains(.notify) { flags.append("notify") }
            if c.properties.contains(.indicate) { flags.append("indicate") }
            print("  \(c.uuid.uuidString): \(flags.joined(separator: ", "))")
        }
        fflush(stdout)
        pending -= 1
        if pending == 0 {
            central.cancelPeripheralConnection(peripheral)
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { exit(0) }
        }
    }
}
let inspector = Inspector()
DispatchQueue.main.asyncAfter(deadline: .now() + 25) {
    inspector.central.stopScan()
    if let p = inspector.target { inspector.central.cancelPeripheralConnection(p) }
    print("Scan finished. Matched controller: \(inspector.target?.name ?? "none")")
    fflush(stdout)
    exit(0)
}
RunLoop.main.run()
