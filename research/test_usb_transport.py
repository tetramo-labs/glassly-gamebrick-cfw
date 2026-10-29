"""Link-layer checks with fake devices: SCSI pass-through routing/discovery and Bulk-Only framing."""
import struct, unittest
from usb_transport import NativeLink, ScsiLink, LinkError, wait_for_controller
from flash_stock import Transport

INQUIRY = bytes.fromhex('120000002400')
BD19 = bytes(8) + b'BD19    ' + b'UBOOT1.00       ' + b'1.00'

class FakeSCSIDev:
    """Mimics jl-uboot-tool's SCSIDev: execute(cdb, data_out, data_in) -> residue."""
    devices = {}
    def __init__(self): self.path = None; self.closed = False
    def open(self, path):
        if path not in self.devices: raise OSError('no such device')
        self.path = path
    def close(self): self.closed = True
    def execute(self, cdb, data_out, data_in):
        dev = self.devices[self.path]; dev.setdefault('log', []).append((bytes(cdb), data_out, None if data_in is None else len(data_in)))
        if cdb[0] == 0x12:
            data_in[:] = dev['inquiry'][:len(data_in)]; return 0
        if data_in is not None:
            reply = dev.get('reply', b'\xa5' * len(data_in)); data_in[:len(reply)] = reply; return len(data_in) - len(reply)
        return 0

class ScsiLinkTests(unittest.TestCase):
    def setUp(self):
        FakeSCSIDev.devices = {
            '/dev/sg0': {'inquiry': bytes(8) + b'ATA     ' + b'Some SSD        ' + b'1.0 '},
            '/dev/sg1': {'inquiry': BD19},
        }
    def test_discovery_matches_the_bd19_bootloader_by_inquiry_only(self):
        link = ScsiLink(FakeSCSIDev, ['/dev/sg9', '/dev/sg0', '/dev/sg1'])
        self.assertTrue(link.try_open()); self.assertEqual(link.path, '/dev/sg1')
        self.assertEqual(FakeSCSIDev.devices['/dev/sg0']['log'], [(INQUIRY, None, 36)], 'only an INQUIRY is sent to other disks')
        FakeSCSIDev.devices['/dev/sg1']['inquiry'] = bytes(8) + b'BD19    ' + b'UDISK           ' + b'1.00'
        self.assertFalse(ScsiLink(FakeSCSIDev, ['/dev/sg1']).try_open(), 'a BD19 that is not UBOOT is not ours')
        self.assertFalse(ScsiLink(FakeSCSIDev, []).try_open())
    def test_commands_route_data_and_reject_short_replies(self):
        link = ScsiLink(FakeSCSIDev, ['/dev/sg1']); link.try_open()
        dev = FakeSCSIDev.devices['/dev/sg1']
        dev['reply'] = b'\xfc\x0a' + bytes(14)
        self.assertEqual(link.execute(b'\xfc\x0a'.ljust(16, b'\xff'), None, 16), dev['reply'])
        self.assertEqual(link.execute(b'\xfb\x06' + bytes(14), b'\x11' * 512, 0), b'')
        self.assertEqual(dev['log'][-1], (b'\xfb\x06' + bytes(14), b'\x11' * 512, None))
        dev['reply'] = b'short'
        with self.assertRaisesRegex(LinkError, 'short'):
            link.execute(b'\xfd\x05'.ljust(16, b'\xff'), None, 256)
        link.close(); self.assertIsNone(link.dev)
        with self.assertRaises(LinkError): link.execute(INQUIRY, None, 36)
    def test_transport_allowlist_runs_before_the_link(self):
        link = ScsiLink(FakeSCSIDev, ['/dev/sg1']); link.try_open()
        t = Transport(link, [0x3000])
        with self.assertRaises(RuntimeError): t.command(0xfb01, (0x3000).to_bytes(4, 'big'))  # writes not enabled
        self.assertEqual(len(FakeSCSIDev.devices['/dev/sg1']['log']), 1, 'nothing but the discovery INQUIRY reached the device')
        self.assertEqual(t.execute(INQUIRY, n=36), BD19)
    def test_wait_for_controller_polls_until_open(self):
        FakeSCSIDev.devices = {}
        link = ScsiLink(FakeSCSIDev, ['/dev/sg1'])
        import time
        with self.assertRaisesRegex(LinkError, 'Timed out'): wait_for_controller(link, time.monotonic() - 1, poll=0)
        FakeSCSIDev.devices = {'/dev/sg1': {'inquiry': BD19}}
        self.assertIs(wait_for_controller(link, time.monotonic() + 5, poll=0), link)

class FakeNative:
    """The IOUSBHost helper: endpoint 1 out, 0x81 in. Records CBWs and answers with data and a CSW."""
    def __init__(self): self.out = []; self.queue = []; self.opens = 0
    def gb_open(self): self.opens += 1; return 0 if self.opens > 1 else -2
    def gb_close(self): pass
    def gb_error(self): return b'none'
    def gb_transfer(self, ep, buf, length, timeout):
        import ctypes
        if ep == 1:
            data = ctypes.string_at(buf, length); self.out.append(data)
            if data[:4] == b'USBC':
                tag, size, flags = struct.unpack_from('<IIB', data, 4)
                if flags & 0x80 and size: self.queue.append(bytes(i % 256 for i in range(size)))
                self.queue.append(struct.pack('<4sIIB', b'USBS', tag, 0, 0))
            return length
        reply = self.queue.pop(0)[:length]; ctypes.memmove(buf, reply, len(reply)); return len(reply)

class NativeLinkTests(unittest.TestCase):
    def test_bulk_only_framing_and_status(self):
        native = FakeNative(); link = NativeLink(native)
        self.assertFalse(link.try_open()); self.assertTrue(link.try_open())
        data = link.execute(b'\xfd\x05' + struct.pack('>IH', 0x1000, 256) + bytes(8), None, 256)
        self.assertEqual(len(data), 256)
        cbw = native.out[0]
        self.assertEqual(cbw[:4], b'USBC'); self.assertEqual(struct.unpack_from('<IIBBB', cbw, 4), (1, 256, 0x80, 0, 16))
        link.execute(b'\xfb\x06' + bytes(14), b'\x22' * 512, 0)
        self.assertEqual(native.out[-1], b'\x22' * 512)
        native.queue.append(struct.pack('<4sIIB', b'USBS', 99, 0, 1))
        with self.assertRaisesRegex(LinkError, 'status'): link.execute(b'\xfc\x0a'.ljust(16, b'\xff'), None, 0)

if __name__ == '__main__': unittest.main()
