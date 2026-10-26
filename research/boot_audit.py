"""Exact-version boot checks added after the 2026-10-25 custom startup failure.

These checks reject known defects; passing is not hardware validation. No USB IO.
"""
import argparse
import json
import struct
from pathlib import Path
from q32s_pcode import Machine

ROOT = Path(__file__).resolve().parent
APP_BASE = 0x1e00120
EMU_CON = 0x1be200
LIMIT_REGISTERS = ((0x1be21c, 0x1be218), (0x1be224, 0x1be220), (0x1be22c, 0x1be228))
BLE_START, BLE_END = 0x1e05248, 0x1e05278

class DebugSetup(Machine):
    """Run only the actual stock debug-register initialization, recording MMIO."""
    def write(self, space, address, size, value):
        if space == 'ram' and 0x1be000 <= address <= 0x1be400 - size:
            for i in range(size):
                self.mem[space, address+i] = (value >> (8*i)) & 255
        else:
            super().write(space, address, size, value)


def execution_limits(app):
    app = bytes(app)
    machine = DebugSetup()
    machine.app = app
    machine.reg('sp', 0x9000)
    machine.execute(0x1e10a5a, 0x1e10a98, max_steps=40)
    control = machine.read('ram', EMU_CON, 4)
    ranges = [(machine.read('ram', lo, 4), machine.read('ram', hi, 4))
              for lo, hi in LIMIT_REGISTERS]
    if any(lo >= hi for lo, hi in ranges):
        raise ValueError('Unrecognized execution-limit initialization')
    return control, ranges


def in_execution_range(address, size, ranges):
    # Treat the upper bound conservatively as exclusive; the failing payload is
    # over 10 KiB beyond it, so endpoint inclusivity cannot explain the failure.
    return any(lo <= address and address + size <= hi for lo, hi in ranges)


def instructions(machine, start, end):
    pc = start
    while pc < end:
        offset = pc - APP_BASE
        ins = machine.ctx.disassemble(machine.app[offset:offset+16], pc, max_instructions=1).instructions[0]
        if pc + ins.length > end:
            raise ValueError(f'Instruction straddles audited boundary: {pc:#x}')
        yield ins
        pc += ins.length


def audit_app(app):
    app = bytes(app)
    control, ranges = execution_limits(app)
    machine = Machine()
    machine.app = app
    errors = []
    if control & 0x10 == 0:
        errors.append({'code': 'PC_PROTECTION_DISABLED', 'detail': 'Do not solve placement by disabling PC protection.'})
    pointer = 0x1e0bcac - APP_BASE
    if app[pointer:pointer+2] != b'\xc0\xff':
        raise ValueError('Unrecognized task creation instruction')
    destinations = [('task entry', struct.unpack_from('<I', app, pointer+2)[0])]
    for address in (0x1e0f194, 0x1e04b86, 0x1e05274):
        ins = next(instructions(machine, address, address+4))
        if ins.mnem not in ('call', 'goto') or not ins.body.startswith('0x'):
            raise ValueError(f'Unrecognized hook instruction at {address:#x}')
        destinations.append((hex(address), int(ins.body, 16)))
    for name, address in destinations:
        if not in_execution_range(address, 2, ranges):
            errors.append({'code': 'HOOK_OUTSIDE_PC_LIMIT', 'site': name, 'target': hex(address)})
    # Decode the entire affected stock function, including the branch that the
    # old test omitted. Its target must still be an instruction boundary.
    block = list(instructions(machine, BLE_START, BLE_END))
    boundaries = {i.addr.offset for i in block}
    for ins in block:
        off = ins.addr.offset - APP_BASE
        for op in machine.ctx.translate(app[off:off+ins.length], ins.addr.offset, max_instructions=1).ops:
            if op.opcode.name not in ('BRANCH', 'CBRANCH'):
                continue
            target = op.inputs[0]
            if target.space.name == 'const':
                continue
            if BLE_START <= target.offset < BLE_END and target.offset not in boundaries:
                errors.append({'code': 'BRANCH_INTO_INSTRUCTION', 'site': hex(ins.addr.offset),
                               'target': hex(target.offset)})
    # Audit every appended instruction, not just entry addresses.
    original_size = 198824
    if len(app) > original_size:
        start = APP_BASE + ((original_size + 15) & ~15)
        invalid = [i.addr.offset for i in instructions(machine, start, APP_BASE+len(app))
                   if not in_execution_range(i.addr.offset, i.length, ranges)]
        if invalid:
            errors.append({'code': 'APPENDED_CODE_OUTSIDE_PC_LIMIT', 'first': hex(invalid[0]),
                           'instruction_count': len(invalid)})
    return {'emu_con': hex(control), 'execution_ranges': [[hex(lo), hex(hi)] for lo, hi in ranges],
            'destinations': {name: hex(address) for name, address in destinations},
            'errors': errors, 'passes_audit': not errors,
            'scope': 'Exact stock version: PC limits, hook destinations, BLE function branch boundaries, appended instructions. Not a complete boot emulator.'}


def require_boot_safe(app):
    report = audit_app(app)
    if report['errors']:
        codes = ', '.join(sorted({e['code'] for e in report['errors']}))
        raise RuntimeError('Custom firmware rejected before USB access: '+codes+'. See docs/boot-failure.md. Stock restore remains available.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', type=Path, nargs='?', default=ROOT/'custom-prepared/app.bin')
    args = parser.parse_args()
    report = audit_app(args.application.read_bytes())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passes_audit'] else 1)

if __name__ == '__main__':
    main()
