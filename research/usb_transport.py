"""Host side of the Jieli USB update mode on macOS, Windows and Linux.

In update mode the controller is a USB mass-storage device (BD19 / UBOOT1.00) that takes
vendor SCSI commands. macOS has no SCSI pass-through for an unmounted removable device, so
the native helper (native-usb.m, IOUSBHost) drives the bulk endpoints and this module frames
the Bulk-Only CBW/CSW itself. Windows and Linux hand the CDB to the kernel's pass-through
(SCSI_PASS_THROUGH_DIRECT on \\\\.\\PhysicalDriveN, SG_IO on /dev/sgN) through the pinned
jl-uboot-tool `scsiio` package, and the OS does the framing. Either way `Link.execute` sees
the same CDB, data and status, and every command still goes through Transport's allowlist.
"""
import ctypes, os, signal, struct, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent

class LinkError(RuntimeError):
    pass

class NativeLink:
    """macOS: Bulk-Only Transport over the IOUSBHost helper."""
    def __init__(self, native):
        self.native = native; self.tag = 0; self.opened = False
    @classmethod
    def load(cls):
        native = ctypes.CDLL(str(ROOT/'native-usb.dylib'))
        native.gb_error.restype = ctypes.c_char_p
        native.gb_transfer.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        return cls(native)
    def try_open(self):
        code = self.native.gb_open()
        if code == 0: self.opened = True; return True
        if code == -2: return False
        raise LinkError(self.native.gb_error().decode())
    def close(self):
        if self.opened: self.native.gb_close(); self.opened = False
    def transfer(self, ep, data_or_size):
        if ep == 1: data = bytes(data_or_size); buf = ctypes.create_string_buffer(data); size = len(data)
        else: size = data_or_size; buf = ctypes.create_string_buffer(size)
        count = self.native.gb_transfer(ep, buf, size, 10000)
        if count < 0: raise LinkError(self.native.gb_error().decode())
        if count != size: raise LinkError(f'Short USB transfer: {count}/{size}')
        return buf.raw[:count]
    def execute(self, cdb, out=None, n=0):
        self.tag += 1; size = len(out) if out is not None else n
        cbw = struct.pack('<4sIIBBB16s', b'USBC', self.tag, size, 0x80 if n else 0, 0, len(cdb), bytes(cdb).ljust(16, b'\0'))
        self.transfer(1, cbw)
        data = b''
        if out is not None: self.transfer(1, out)
        elif n: data = self.transfer(0x81, n)
        csw = self.transfer(0x81, 13)
        if struct.unpack('<4sIIB', csw) != (b'USBS', self.tag, 0, 0): raise LinkError('Failed USB command status')
        return data

class ScsiLink:
    """Windows and Linux: the kernel's SCSI pass-through on the update-mode disk device."""
    def __init__(self, scsi_dev_class=None, candidates=None):
        if scsi_dev_class is None:
            sys.path.insert(0, str(ROOT/'jl-uboot-tool'))
            from scsiio import SCSIDev
            scsi_dev_class = SCSIDev
        self.SCSIDev = scsi_dev_class; self.candidates = candidates; self.dev = None; self.path = None
    @staticmethod
    def candidate_paths():
        if sys.platform == 'win32':
            return [f'\\\\.\\PhysicalDrive{i}' for i in range(32)]
        if sys.platform.startswith('linux'):
            return sorted(str(p) for p in Path('/dev').glob('sg*'))
        return []
    def try_open(self):
        for path in (self.candidates if self.candidates is not None else self.candidate_paths()):
            dev = self.SCSIDev()
            try:
                dev.open(path)
            except Exception:
                continue
            try:
                inquiry = bytearray(36)
                dev.execute(bytes.fromhex('120000002400'), None, inquiry)
                if inquiry[8:16].decode('ascii', 'replace').strip() == 'BD19' and inquiry[16:32].decode('ascii', 'replace').strip() == 'UBOOT1.00':
                    self.dev = dev; self.path = path; return True
            except Exception:
                pass
            dev.close()
        return False
    def close(self):
        if self.dev is not None: self.dev.close(); self.dev = None
    def execute(self, cdb, out=None, n=0):
        if self.dev is None: raise LinkError('Device not open')
        try:
            if out is not None:
                residue = self.dev.execute(bytes(cdb), bytes(out), None)
                return b''
            if n:
                data = bytearray(n); residue = self.dev.execute(bytes(cdb), None, data)
            else:
                residue = self.dev.execute(bytes(cdb), None, None); data = bytearray()
        except Exception as e:
            raise LinkError(f'SCSI command failed: {e}') from e
        if residue: raise LinkError(f'SCSI command returned {residue} byte(s) short')
        return bytes(data)

def open_link():
    if sys.platform == 'darwin': return NativeLink.load()
    if sys.platform == 'win32' or sys.platform.startswith('linux'): return ScsiLink()
    raise LinkError(f'Unsupported platform: {sys.platform}')

def wait_for_controller(link, deadline, poll=0.25):
    """Poll until the controller's update mode is reachable; the caller prints the instructions."""
    while True:
        if link.try_open(): return link
        if time.monotonic() > deadline: raise LinkError('Timed out waiting for the controller')
        time.sleep(poll)

def update_mode_instructions():
    where = {'win32': 'this PC', 'darwin': 'this Mac'}.get(sys.platform, 'this computer')
    return f'With the controller switched ON and plugged into {where}, hold Pairing + B for about two seconds until its light goes out, then release both.'

def require_privileges():
    """USB bulk access (macOS), raw disk access (Windows) and /dev/sg (Linux) all need elevation."""
    if sys.platform == 'win32':
        try: admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception: admin = False
        if not admin: raise LinkError('Run this from a terminal opened as Administrator (raw disk access).')
    elif os.geteuid() != 0:
        raise LinkError('Run this with sudo (USB device access).')

def start_watchdog(seconds):
    if hasattr(signal, 'alarm'): signal.alarm(seconds)

def give_back_ownership(path, owner_of):
    """Files created under sudo belong to root; hand them to the checkout's owner."""
    if sys.platform == 'win32' or os.geteuid() != 0: return
    owner = Path(owner_of).stat().st_uid
    for p in [Path(path)] + list(Path(path).iterdir()):
        os.chown(p, owner, -1)
