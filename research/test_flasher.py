"""Offline checks for the one-shot flasher against the unit2 artifacts. No USB access."""
import contextlib, io, os, unittest
os.environ.setdefault('GB_DEVICE', 'unit2')
from pathlib import Path
from gamebrick_flasher import FINGERPRINTS, CUSTOM_APP_SHA, classify, custom_application, fingerprint, oem_application, oem_archive, plan
from flash_gamebrick import program_with_plan
from stock_update import digest, OEM_SHA
from test_custom_image import NOR
ROOT = Path(__file__).resolve().parent

class FlasherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.factory = (ROOT/'device-backup-20261028-192851/flash-pass1.bin').read_bytes()
        cls.stock = (ROOT/'stock-update-prepared/unit2/stock-app-device-layout.bin').read_bytes()
        cls.custom = (ROOT/'custom-prepared/unit2/custom-device-layout.bin').read_bytes()
        cls.oem = oem_application(oem_archive(ROOT/'stock-update.zip', log=lambda *_: None))

    def test_official_application_and_patch_are_pinned(self):
        self.assertEqual(digest(self.oem), OEM_SHA)
        self.assertEqual(oem_application(), self.oem, 'the committed official application is the archive\'s')
        patched = custom_application(self.oem)
        self.assertEqual(digest(patched), CUSTOM_APP_SHA)
        self.assertEqual(custom_application(), patched, 'the committed Glassly application is the patched build')
        self.assertEqual(patched, (ROOT/'custom-prepared/unit2/app.bin').read_bytes(), 'same bytes as the reviewed per-unit build')
        with self.assertRaises(RuntimeError):
            custom_application(b'\0' + self.oem[1:])

    def test_fingerprints_ignore_storage_and_classify_every_known_state(self):
        self.assertEqual(classify(self.factory), 'factory')
        self.assertEqual(classify(self.stock), 'stock')
        self.assertEqual(classify(self.custom), 'custom')
        self.assertEqual(classify((ROOT/'custom-flash-unit2-20261028-193401/target.bin').read_bytes()), 'custom')
        self.assertEqual(classify((ROOT/'device-backup-20261022-233350/flash-pass1.bin').read_bytes()), 'factory', 'unit1 shares the fingerprint')
        drifted = bytearray(self.factory); drifted[0x7a123] ^= 0xFF; drifted[0x7f000] = 0x12
        self.assertEqual(fingerprint(bytes(drifted)), fingerprint(self.factory))
        for address in (0, 0x2140, 0x79fff):
            bad = bytearray(self.factory); bad[address] ^= 1
            self.assertEqual(classify(bytes(bad)), 'unknown')
        self.assertEqual(len(FINGERPRINTS), 4)

    def test_plans_from_every_state_reach_the_reviewed_images(self):
        rebuilt = plan(self.factory, self.oem, 'install', custom_application(self.oem))
        from_factory = plan(self.factory, self.oem, 'install')
        self.assertEqual(rebuilt['target'], from_factory['target'], 'committed and rebuilt applications agree')
        self.assertEqual(from_factory['state'], 'factory')
        self.assertEqual(from_factory['target'], self.custom, 'factory straight to the reviewed unit2 custom image')
        self.assertEqual(from_factory['stock'], self.stock)
        self.assertEqual(len(from_factory['changed_sectors']), 50)
        from_stock = plan(self.stock, self.oem, 'install')
        self.assertEqual(from_stock['target'], self.custom)
        self.assertEqual([hex(a) for a in from_stock['changed_sectors']], ['0x2000','0x6000','0x7000','0xd000','0x11000','0x12000','0x32000','0x33000'])
        from_custom = plan(self.custom, self.oem, 'install')
        self.assertEqual(from_custom['changed_sectors'], [])
        back = plan(self.custom, self.oem, 'restore')
        self.assertEqual(back['target'], self.stock)
        self.assertEqual(plan(self.factory, self.oem, 'restore')['target'], self.stock)
        # Live storage rides along untouched.
        drifted = bytearray(self.factory); drifted[0x7a123] ^= 0xFF
        live = plan(bytes(drifted), self.oem, 'install')
        self.assertEqual(live['target'][0x7a000:], bytes(drifted)[0x7a000:])
        self.assertEqual(live['target'][:0x7a000], self.custom[:0x7a000])
        for state in ('withdrawn', 'unknown'):
            image = bytearray((ROOT/'custom-prepared/custom-device-layout-withdrawn-20261025.bin').read_bytes() if state == 'withdrawn' else self.factory)
            if state == 'unknown': image[0x2140] ^= 1
            with self.assertRaisesRegex(RuntimeError, 'Unrecognised'):
                plan(bytes(image), self.oem, 'install')

    def test_programs_factory_to_custom_and_back_with_full_verification(self):
        oem = self.oem
        device = NOR(self.factory, range(0, 0x80000, 4096))
        saved = {}
        with contextlib.redirect_stdout(io.StringIO()):
            report = program_with_plan(device, lambda current: (current, plan(current, oem, 'install')['target']), saved.__setitem__)
        self.assertTrue(report['full_readback_verified'])
        self.assertEqual(bytes(device.data), self.custom)
        self.assertEqual(saved['flash-pass1.bin'], self.factory)
        self.assertEqual(device.erased[-1], 0x2000, 'the header sector is committed last')
        self.assertFalse(device.writes_enabled)
        with contextlib.redirect_stdout(io.StringIO()):
            again = program_with_plan(device, lambda current: (current, plan(current, oem, 'install')['target']), saved.__setitem__)
        self.assertEqual(again['writes'], 0)
        with contextlib.redirect_stdout(io.StringIO()):
            program_with_plan(device, lambda current: (current, plan(current, oem, 'restore')['target']), saved.__setitem__)
        self.assertEqual(bytes(device.data), self.stock)

    def test_unstable_or_unknown_flash_never_enables_writes(self):
        oem = self.oem
        class Unstable(NOR):
            reads = 0
            def read(self, a, n):
                self.reads += 1
                if self.reads == 2: self.data[0x7a000] ^= 1
                return super().read(a, n)
        shaky = Unstable(self.factory, range(0, 0x80000, 4096))
        with self.assertRaises(RuntimeError), contextlib.redirect_stdout(io.StringIO()):
            program_with_plan(shaky, lambda current: (current, plan(current, oem, 'install')['target']), lambda n, d: None)
        self.assertFalse(shaky.erased)
        bad = bytearray(self.factory); bad[0x40000] ^= 1
        unknown = NOR(bytes(bad), range(0, 0x80000, 4096))
        with self.assertRaises(RuntimeError), contextlib.redirect_stdout(io.StringIO()):
            program_with_plan(unknown, lambda current: (current, plan(current, oem, 'install')['target']), lambda n, d: None)
        self.assertFalse(unknown.erased)

if __name__ == '__main__': unittest.main()
