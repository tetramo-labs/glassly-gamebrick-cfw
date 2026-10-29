"""Regressions for the image flashed on 2026-10-25 and the replacement candidate. No USB access."""
import os
os.environ.setdefault('GB_DEVICE', 'unit1')
import contextlib
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
from boot_audit import APP_BASE, audit_app, execution_limits, in_execution_range
from test_payload_q32s import PayloadMachine
from custom_image import BASE, LIMIT, SECTORS, DEST
from stock_update import OUT
from stock_update import entry, digest
from jltech.cipher import jl_sfc_cipher

ROOT = Path(__file__).resolve().parent


def captured_application():
    flash = (ROOT/'custom-flash-20261025-135838/target.bin').read_bytes()
    assert digest(flash) == 'bec28bd21195de6d5ef50a0fb163a5dd8d669aeba2aa38e79b8ca37a2cc2073b'
    plain = bytearray(flash)
    jl_sfc_cipher(plain, BASE, LIMIT-BASE, BASE, 0x190d)
    record = entry(plain, BASE+32)
    app = bytes(plain[BASE+record[2]:BASE+record[2]+record[3]])
    assert digest(app) == '8b3cf5bff313e27c4da630bf8759df7217f8a8ed88bcbf83d18c280c09b43221'
    return app


class ProtectedPayload(PayloadMachine):
    def before_instruction(self, pc):
        if not in_execution_range(pc, 2, self.execution_ranges):
            raise RuntimeError(f'PC outside configured execution ranges: {pc:#x}')


class BootAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = (ROOT/'unpacked/files/app.bin').read_bytes()
        cls.failed = captured_application()
        cls.candidate = (DEST/'app.bin').read_bytes()
        cls.stock_image = (OUT/'stock-app-device-layout.bin').read_bytes()
        cls.custom_image = (DEST/'custom-device-layout.bin').read_bytes()

    def codes(self, app):
        return {e['code'] for e in audit_app(app)['errors']}

    def test_stock_passes_and_flashed_image_fails(self):
        self.assertTrue(audit_app(self.stock)['passes_audit'])
        self.assertEqual(self.codes(self.failed), {'HOOK_OUTSIDE_PC_LIMIT',
            'APPENDED_CODE_OUTSIDE_PC_LIMIT', 'BRANCH_INTO_INSTRUCTION', 'FLASH_TEXT_LIMIT_MISMATCH'})

    def test_replacement_candidate_passes_audit(self):
        report = audit_app(self.candidate)
        self.assertEqual(report['errors'], [])
        end = APP_BASE + len(self.candidate)
        self.assertEqual(report['execution_ranges'][0], [hex(APP_BASE), hex(end)])
        self.assertEqual(report['execution_ranges'][1:], [['0x40c0','0x61a8'],['0x100000','0x110000']])
        # Every hook destination and the stock BLE call stay inside the configured range.
        for address in report['destinations'].values():
            self.assertTrue(APP_BASE <= int(address,16) < end)
        self.assertEqual(report['destinations']['0x1e05274'], '0x1e0520c')
        self.assertEqual(self.candidate[0x1e05274-APP_BASE:0x1e05278-APP_BASE], self.stock[0x1e05274-APP_BASE:0x1e05278-APP_BASE])

    def test_candidate_limit_may_not_differ_from_application_end(self):
        for value, code in [(APP_BASE+len(self.candidate)+32, 'FLASH_TEXT_LIMIT_MISMATCH'),
                            (APP_BASE+len(self.candidate)-32, 'FLASH_TEXT_LIMIT_MISMATCH'),
                            (0x2000000, 'FLASH_TEXT_LIMIT_MISMATCH')]:
            with self.subTest(limit=hex(value)):
                app = bytearray(self.candidate)
                struct.pack_into('<I', app, 0x1e10a92-APP_BASE, value)
                self.assertIn(code, self.codes(app))
        for offset, value, code in [(0x1e10a8a, APP_BASE-0x120, 'EXECUTION_LIMITS_CHANGED'),
                                    (0x1e10a82, 0x8000, 'EXECUTION_LIMITS_CHANGED'),
                                    (0x1e00174, APP_BASE+len(self.candidate), 'STARTUP_DATA_COPY_CHANGED')]:
            with self.subTest(offset=hex(offset)):
                app = bytearray(self.candidate)
                struct.pack_into('<I', app, offset-APP_BASE, value)
                self.assertIn(code, self.codes(app))
        # Stock keeps its original limit; a stock-sized image with a raised limit is rejected.
        app = bytearray(self.stock)
        struct.pack_into('<I', app, 0x1e10a92-APP_BASE, APP_BASE+len(self.candidate))
        self.assertIn('FLASH_TEXT_LIMIT_MISMATCH', self.codes(app))

    def test_candidate_hooks_execute_under_protected_fetch(self):
        for site, stop, regs in [(0x1e309d0, 0x1e0ee70, {}), (0x1e0f194, 0x1e0f198, {}),
                                 (0x1e04b86, 0x1e04b8a, {'r0':3,'r1':0x55,'r2':1}),
                                 (0x1e05248, 0x1e001d0, {'r0':7,'r1':9})]:
            with self.subTest(site=hex(site)):
                m = ProtectedPayload(); m.app = self.candidate
                _, m.execution_ranges = execution_limits(m.app)
                m.reg('sp',0x9000); m.reg('rets',stop)
                for i in range(0x8e00,0x9004): m.write('ram',i,1,0)
                m.write('ram',0x84b,1,0); m.write('ram',0x29e2,2,3)
                for name, value in regs.items(): m.reg(name, value)
                m.execute(site, stop, max_steps=400)
                self.assertTrue(m.handlers or m.stub_calls or site == 0x1e309d0)

    def test_candidate_unchanged_ble_state_returns_like_stock(self):
        for state in (0,1,7):
            with self.subTest(state=state):
                for app in (self.candidate, self.stock):
                    m = PayloadMachine(); m.app = app
                    m.reg('sp',0x9000); m.reg('rets',0x1e001d0)
                    m.reg('r0',state); m.reg('r1',9); m.write('ram',0x84b,1,state)
                    m.write('ram',state+0x36,2,0xaaaa); m.write('ram',0x40b8,4,5)
                    m.execute(0x1e05248,0x1e001d0,max_steps=20)
                    self.assertEqual(m.read('ram',state+0x36,2),0xaaaa)
                    self.assertEqual(m.reg('sp'),0x9000)
                    self.assertEqual(m.stub_calls,[])
                    self.assertEqual(m.read('ram',0x40b8,4),5)  # Epoch untouched when state is unchanged.
                # A changed state on the candidate sends the event and advances the epoch once.
                m = PayloadMachine(); m.app = self.candidate
                m.reg('sp',0x9000); m.reg('rets',0x1e001d0)
                m.reg('r0',7); m.reg('r1',9); m.write('ram',0x84b,1,(state+1)&0xff if state==7 else state+8)
                m.write('ram',0x40b8,4,5)
                m.execute(0x1e05248,0x1e001d0,max_steps=40)
                self.assertEqual([c[0] for c in m.stub_calls],[0x1e197d0,0x1e0520c])
                self.assertEqual(m.stub_calls[1][1][:3],[0x424c4500,7,9])
                self.assertEqual(m.read('ram',0x40b8,4),6)
                self.assertEqual(m.read('ram',0x84b,1),7)
                self.assertEqual(m.reg('sp'),0x9000); self.assertEqual(m.reg('r0'),23)

    def test_limits_are_derived_from_boot_instructions(self):
        control, ranges = execution_limits(self.failed)
        self.assertEqual(control, 0x80000017)
        self.assertEqual(ranges, [(0x1e00120,0x1e2dfc8),(0x40c0,0x61a8),(0x100000,0x110000)])
        # In-memory experiment only: widening the limit does not fix the branch.
        widened = bytearray(self.failed)
        struct.pack_into('<I', widened, 0x1e10a92-APP_BASE, APP_BASE+len(widened))
        self.assertEqual(self.codes(widened), {'BRANCH_INTO_INSTRUCTION'})

    def test_each_custom_hook_fails_protected_fetch(self):
        for site in (0x1e309d0,0x1e0f194,0x1e04b86,0x1e05248):
            with self.subTest(site=hex(site)):
                m = ProtectedPayload();m.app = self.failed
                _,m.execution_ranges = execution_limits(m.app)
                m.reg('sp',0x9000);m.reg('rets',0x1e001d0)
                # The lifecycle state differs so this path takes the new tail.
                m.reg('r0',7);m.reg('r1',9);m.write('ram',0x84b,1,0)
                with self.assertRaisesRegex(RuntimeError,'PC outside configured'):
                    m.execute(site,0x1e001d0)

    def test_unchanged_ble_state_corrupts_ram_before_falling_through(self):
        for state in (0,1,7):
            with self.subTest(state=state):
                m = PayloadMachine();m.app = self.failed
                m.reg('sp',0x9000);m.reg('rets',0x1e001d0)
                m.reg('r0',state);m.reg('r1',9);m.write('ram',0x84b,1,state)
                m.write('ram',state+0x36,2,0xaaaa)
                m.execute(0x1e05248,0x1e05278,max_steps=20)
                self.assertEqual(m.read('ram',state+0x36,2),state)
                self.assertEqual(m.reg('sp'),0x8ff0)  # Saved frame was not popped.
                self.assertEqual(m.stub_calls,[])
                # Same input on stock returns, preserving both RAM and the stack.
                s = PayloadMachine();s.app = self.stock
                s.reg('sp',0x9000);s.reg('rets',0x1e001d0)
                s.reg('r0',state);s.reg('r1',9);s.write('ram',0x84b,1,state)
                s.write('ram',state+0x36,2,0xaaaa)
                s.execute(0x1e05248,0x1e001d0,max_steps=20)
                self.assertEqual(s.read('ram',state+0x36,2),0xaaaa)
                self.assertEqual(s.reg('sp'),0x9000)

    def test_restoring_epilogue_only_does_not_fix_code_placement(self):
        app = bytearray(self.failed);off=0x1e05274-APP_BASE
        app[off:off+4] = self.stock[off:off+4]
        codes = self.codes(app)
        self.assertNotIn('BRANCH_INTO_INSTRUCTION', codes)
        self.assertIn('HOOK_OUTSIDE_PC_LIMIT', codes)

    def test_disabling_protection_is_rejected(self):
        app = bytearray(self.failed)
        struct.pack_into('<I', app, 0x1e10a60-APP_BASE, 0x80000007)
        self.assertIn('PC_PROTECTION_DISABLED', self.codes(app))

    def test_cli_install_and_check_refuse_before_usb_or_log_directory(self):
        import flash_custom
        metadata = {'changed_sectors':SECTORS}
        stock, custom = self.stock_image, self.custom_image
        for mode in ('install','check'):
            with self.subTest(mode=mode), patch.object(sys,'argv',['flash_custom.py',mode]), \
                 patch.object(flash_custom,'prepare',return_value=(stock,custom,metadata)), \
                 patch.object(flash_custom,'candidate_application',return_value=self.failed), \
                 patch.object(flash_custom.ctypes,'CDLL') as usb, \
                 patch.object(Path,'mkdir') as mkdir:
                with self.assertRaisesRegex(RuntimeError,'rejected before USB'):
                    flash_custom.main()
                usb.assert_not_called();mkdir.assert_not_called()

    def test_restore_remains_available_for_rejected_application(self):
        from custom_runtime import program_preserving_storage
        from test_custom_image import NOR
        stock, custom = self.stock_image, self.custom_image
        installed = (ROOT/'custom-flash-20261025-135838/target.bin').read_bytes()
        expected = (ROOT/'custom-flash-20261025-135838/restore-stock.bin').read_bytes()
        device = NOR(installed,SECTORS)
        with contextlib.redirect_stdout(io.StringIO()):
            result = program_preserving_storage(device,stock,custom,'restore',lambda name,data:None)
        self.assertTrue(result['full_readback_verified'])
        self.assertEqual(bytes(device.data),expected)

if __name__ == '__main__':
    unittest.main()
