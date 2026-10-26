import Foundation
import CoreBluetooth
import GameController

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
            let connected = central.retrieveConnectedPeripherals(withServices: [CBUUID(string: "1812"), CBUUID(string: "180F"), CBUUID(string: "180A")])
            for p in connected {
                print("Already connected: \(p.name ?? "unknown")")
                if target == nil && (p.name?.localizedCaseInsensitiveContains("xbox") == true || p.name?.localizedCaseInsensitiveContains("iine") == true) {
                    target = p
                    p.delegate = self
                    central.connect(p)
                }
            }
            if target == nil { central.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false]) }
            print("Scanning BLE advertisements for 300 seconds...")
            fflush(stdout)
        }
    }
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? peripheral.name ?? "(unnamed)"
        if seen.insert(peripheral.identifier).inserted {
            if name.lowercased().contains("iine") || name.lowercased().contains("controller") { print("Found: \(name) | RSSI \(RSSI) | services \(advertisementData[CBAdvertisementDataServiceUUIDsKey] ?? [])") }
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
    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        print("Disconnected: \(peripheral.name ?? "unknown"); \(String(describing: error))")
        target = nil
        seen.removeAll()
        central.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
        fflush(stdout)
    }
    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        print("Connection failed: \(String(describing: error))")
        fflush(stdout)
    }
    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        print("NOTIFY \(characteristic.uuid.uuidString): enabled=\(characteristic.isNotifying), error=\(String(describing: error))")
        fflush(stdout)
    }
    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        let data = characteristic.value ?? Data()
        let hex = data.map { String(format: "%02x", $0) }.joined(separator: " ")
        let decoded = characteristic.uuid.uuidString.hasPrefix("2A") ? (String(data: data, encoding: .utf8) ?? "") : ""
        print("BLE \(characteristic.uuid.uuidString): \(hex) \(decoded) error=\(String(describing: error))")
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
            if ["AE42", "AE02"].contains(c.uuid.uuidString) {
                peripheral.setNotifyValue(true, for: c)
            }
            if ["2A29", "2A24", "2A26", "2A27", "2A28", "2A50"].contains(c.uuid.uuidString) {
                peripheral.readValue(for: c)
            }
        }
        fflush(stdout)
        pending -= 1
        if pending == 0 {
            print("Service enumeration complete; listening for controller input")
        }
    }
}
func observe(_ controller: GCController) {
    print("GameController: vendor=\(controller.vendorName ?? "unknown"), category=\(controller.productCategory), extended=\(controller.extendedGamepad != nil), micro=\(controller.microGamepad != nil)")
    for (name, element) in controller.physicalInputProfile.elements.sorted(by: { $0.key < $1.key }) {
        print("  Input element: \(name) [\(type(of: element))]")
    }
    controller.physicalInputProfile.valueDidChangeHandler = { profile, element in
        let names = profile.elements.filter { $0.value === element }.map { $0.key }.joined(separator: ",")
        if let b = element as? GCControllerButtonInput { print("INPUT \(names): \(b.value)") }
        else if let d = element as? GCControllerDirectionPad { print("INPUT \(names): x=\(d.xAxis.value), y=\(d.yAxis.value)") }
        else { print("INPUT \(names)") }
        fflush(stdout)
    }
    fflush(stdout)
}
GCController.shouldMonitorBackgroundEvents = true
let observer = NotificationCenter.default.addObserver(forName: .GCControllerDidConnect, object: nil, queue: .main) { n in
    if let c = n.object as? GCController { observe(c) }
}
for c in GCController.controllers() { observe(c) }
let inspector = Inspector()
DispatchQueue.main.asyncAfter(deadline: .now() + 300) {
    inspector.central.stopScan()
    if let p = inspector.target { inspector.central.cancelPeripheralConnection(p) }
    print("Scan finished. Matched controller: \(inspector.target?.name ?? "none")")
    fflush(stdout)
    exit(0)
}
let stopTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
    if FileManager.default.fileExists(atPath: "/tmp/gamebrick-stop") {
        inspector.central.stopScan()
        if let p = inspector.target { inspector.central.cancelPeripheralConnection(p) }
        print("Stopped diagnostic listener")
        fflush(stdout)
        exit(0)
    }
}
RunLoop.main.run()
