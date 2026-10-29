"""Package exact-version task/CCC hooks into the retained device layout, offline."""
from pathlib import Path
import json, struct
from stock_update import ROOT, NAME, BACKUP, OEM_SHA, BASE, LIMIT, OUT, build, digest, require, entry
from stock_update import prepare as prepare_stock
from device_profile import STOCK_SHA, CUSTOM_SHA, CUSTOM_OUT as DEST
from jltech.cipher import jl_sfc_cipher

APP_BASE = 0x1e00120
# The replacement candidate changes the eight sectors below on every unit. Per-unit
# stock/custom hashes are pinned in devices.json and re-reviewed after each rebuild.
SECTORS = [0x2000, 0x6000, 0x7000, 0xd000, 0x11000, 0x12000, 0x32000, 0x33000]

def branch(src, dst, call=True):
    delta = dst - (src + 4)
    require(delta % 2 == 0 and -(1 << 22) <= delta < (1 << 22), 'Branch out of range')
    return struct.pack('<HH', (0xf380 if call else 0xf3c0) | ((delta >> 17) & 63), (delta >> 1) & 65535)

def patch_app(app, payload, manifest, decode=True):
    """Apply the reviewed hooks to the OEM application. `decode` re-verifies every changed
    instruction with the extended SLEIGH description (research checkouts); the end-user
    flasher skips that and pins the resulting application hash instead."""
    require(digest(app) == OEM_SHA and len(app) == 198824, 'Unexpected stock app')
    require(digest(payload) == manifest['payload_sha256'], 'Payload hash differs from verified ELF')
    for name, expected in manifest['sources'].items():
        require(digest((ROOT.parent / name).read_bytes()) == expected, 'Source changed since build: ' + name)
    symbols = {k: int(v, 16) for k, v in manifest['symbols'].items()}
    append = (len(app) + 15) & ~15
    require(APP_BASE + append == symbols['gb_task_entry'], 'Payload placement mismatch')
    patches = []
    output = bytearray(app)
    def put(addr, before, after, purpose):
        off = addr - APP_BASE
        require(len(before) == len(after) and output[off:off+len(before)] == before, 'Unexpected patch site: ' + hex(addr))
        output[off:off+len(before)] = after
        patches.append({'address': hex(addr), 'offset': hex(off), 'before': before.hex(), 'after': after.hex(), 'purpose': purpose})
    # Preserve the task's original entry instructions. Redirect only its creation pointer.
    put(0x1e0bcac, bytes.fromhex('c0ff68eee001'), b'\xc0\xff' + struct.pack('<I', symbols['gb_task_entry']), 'Create task through state-initializing entry')
    put(0x1e0bcb6, bytes.fromhex('03fb0008'), bytes.fromhex('03fb4008'), 'Increase task stack request from 0x800 to 0x840; preserve headroom')
    for site, target, symbol in [(0x1e0f194,0x1e0ce10,'gb_task_tick'), (0x1e04b86,0x1e14114,'gb_ccc_changed')]:
        put(site, branch(site,target), branch(site,symbols[symbol]), symbol)
    # Hook the two register moves before the BLE event call. The stock two-byte call and
    # the epilogue at 0x1e05276 remain, so the unchanged-state branch at 0x1e05256 is intact.
    put(0x1e05270, bytes.fromhex('51084208'), branch(0x1e05270,symbols['gb_ble_tail'],False), 'gb_ble_tail')
    require(output[0x1e05274-APP_BASE:0x1e05278-APP_BASE] == bytes.fromhex('cb175601'), 'BLE call/epilogue must stay intact')
    require(output[0x1e05256-APP_BASE:0x1e0525a-APP_BASE] == bytes.fromhex('52f20e00'), 'Unchanged-state branch must still target 0x1e05276')
    # The payload is appended after the application image, beyond the linked text end that
    # debug_init programs as the flash PC limit. Raise that one immediate to the new end of
    # the application, together with the placement. The startup data-copy source that uses
    # the same constant at 0x1e00174 is not touched.
    end = append + len(payload)
    end += -end % 32
    put(0x1e10a90, bytes.fromhex('c0ffc8dfe201'), b'\xc0\xff' + struct.pack('<I', APP_BASE + end), 'flash_text_limit')
    require(output[0x1e00172-APP_BASE:0x1e00178-APP_BASE] == bytes.fromhex('c1ffc8dfe201'), 'Startup data copy source changed')
    # Stock BSS ends at 0x40b8; relocated code starts at 0x40c0. Reserve four padding bytes.
    require(app[0x12:0x1e] == bytes.fromhex('c1ffc01c0000c2fff8230000'), 'Startup BSS layout mismatch')
    require(app[0x72:0x78] == bytes.fromhex('c0ffc0400000'), 'RAM-code destination mismatch')
    put(0x1e00138, bytes.fromhex('c2fff8230000'), bytes.fromhex('c2fffc230000'), 'Zero reserved epoch word at 0x40b8; stop before RAM code')
    require(0x1cc0 + 0x23fc == 0x40bc < 0x40c0, 'Epoch overlaps RAM code')
    output.extend(b'\0' * (append - len(output)))
    output.extend(payload)
    output.extend(b'\0' * (-len(output) % 32))
    require(len(output) == end, 'Execution limit does not match the application end')
    changed = {i for i,(a,b) in enumerate(zip(app,output)) if a != b}
    allowed = {i for p in patches for i in range(int(p['offset'],16), int(p['offset'],16)+len(bytes.fromhex(p['before'])))}
    require(changed <= allowed, 'Unlisted original application change')
    if not decode:
        return bytes(output), patches
    # Independently decode every changed instruction using the extended SLEIGH description.
    import pypcode
    arch = pypcode.Arch('Jieli', str(ROOT/'q32s-analysis/processor/data/languages/JieLi.ldefs'))
    ctx = pypcode.Context(next(x for x in arch.languages if x.id == 'q32s:LE:32:default'))
    for patch in patches:
        addr = int(patch['address'], 16)
        instruction = ctx.disassemble(bytes.fromhex(patch['after']), addr, max_instructions=1).instructions[0]
        require(instruction.length == len(bytes.fromhex(patch['after'])), 'Patch instruction width changed')
        patch['decoded'] = instruction.mnem + ' ' + instruction.body
        if patch['purpose'] in symbols:
            require(instruction.mnem == ('goto' if patch['purpose'] == 'gb_ble_tail' else 'call') and int(instruction.body,16) == symbols[patch['purpose']], 'Hook target mismatch')
        elif patch['purpose'] == 'flash_text_limit':
            require(instruction.mnem == 'mov' and instruction.body == f'r0, #{APP_BASE+end:#x}', 'Execution limit immediate mismatch')
    return bytes(output), patches

def prepare():
    original, stock, _ = prepare_stock()
    require((BACKUP.parent/'flash-pass2.bin').read_bytes() == original, 'Backup copies differ')
    require(digest(stock) == STOCK_SHA, 'Installed stock reference mismatch')
    app = (ROOT/'unpacked/files/app.bin').read_bytes()
    require(build(original, app) == stock, 'Stock layout reconstruction differs')
    payload = (ROOT/'q32s-analysis/vendor-payload.bin').read_bytes()
    manifest = json.loads((ROOT.parent/'docs/evidence/q32s-payload.json').read_text())
    patched, patches = patch_app(app, payload, manifest)
    custom = build(original, patched)
    # Independent retained-layout extraction/CRC validation, including moved resources.
    decoded = bytearray(custom)
    jl_sfc_cipher(decoded, BASE, LIMIT-BASE, BASE, 0x190d)
    area, application, cfg = (entry(decoded, BASE+i) for i in (0,32,64))
    from jltech.crc import jl_crc16
    require(jl_crc16(decoded[BASE+32:BASE+area[3]]) == area[1], 'Area CRC')
    extracted = bytes(decoded[BASE+application[2]:BASE+application[2]+application[3]])
    require(extracted == patched and jl_crc16(extracted) == application[1], 'Application extraction/CRC')
    p11 = entry(decoded, BASE+area[3])
    require(bytes(decoded[BASE+cfg[2]:BASE+cfg[2]+cfg[3]]) == (ROOT/'unpacked/files/cfg_tool.bin').read_bytes(), 'Configuration changed')
    require(bytes(decoded[BASE+area[3]+32:BASE+area[3]+p11[3]]) == (ROOT/'unpacked/files/p11_code.bin').read_bytes(), 'P11 changed')
    end = BASE+area[3]+p11[3]
    require(custom[:BASE] == stock[:BASE] and custom[end:] == stock[end:], 'Protected bytes changed')
    sectors = [a for a in range(0,len(stock),4096) if stock[a:a+4096] != custom[a:a+4096]]
    require(sectors == SECTORS, 'Changed sectors differ from the reviewed set')
    require(digest(custom) == CUSTOM_SHA, f'Custom image for {NAME} differs from its pinned hash {CUSTOM_SHA}: got {digest(custom)}')
    from boot_audit import audit_app
    audit = audit_app(patched)
    report = {'status':('REPLACEMENT CANDIDATE; passes offline boot audit; not flashed; hardware validation pending' if audit['passes_audit'] else 'REJECTED by boot audit; install blocked'), 'boot_audit':audit, 'device':NAME, 'stock_sha256':STOCK_SHA, 'target_sha256':digest(custom), 'app_sha256':digest(patched), 'app_size':len(patched), 'payload_size':len(payload), 'changed_sectors':sectors, 'patches':patches, 'state':{'task_stack_extra':40,'task_stack_request_before':2048,'task_stack_request_after':2112,'epoch_address':'0x40b8','queue_capacity':16}, 'preserved':'All bytes outside used active application area; config and P11 content retained, file headers/offsets updated'}
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST/'app.bin').write_bytes(patched)
    (DEST/'custom-device-layout.bin').write_bytes(custom)
    (DEST/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT.parent/f'docs/evidence/custom-image-{NAME}.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Custom candidate for {NAME}: {len(payload)}-byte payload, {len(sectors)} changed sectors, SHA256 {digest(custom)}; boot audit {"passed" if audit["passes_audit"] else "FAILED"}')
    return stock, custom, report
if __name__ == '__main__': prepare()
