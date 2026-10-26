"""Package exact-version task/CCC hooks into the retained device layout, offline."""
from pathlib import Path
import json, struct
import pypcode
from stock_update import ROOT, BACKUP, OEM_SHA, BASE, LIMIT, OUT, build, digest, require, entry
from jltech.cipher import jl_sfc_cipher

APP_BASE = 0x1e00120
STOCK_SHA = 'dfbaeffd4e4cb2c940481cab918b55e29c2eea47107e3214ed12af96b03e8465'
DEST = ROOT / 'custom-prepared'

def branch(src, dst, call=True):
    delta = dst - (src + 4)
    require(delta % 2 == 0 and -(1 << 22) <= delta < (1 << 22), 'Branch out of range')
    return struct.pack('<HH', (0xf380 if call else 0xf3c0) | ((delta >> 17) & 63), (delta >> 1) & 65535)

def patch_app(app, payload, manifest):
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
    put(0x1e05274, bytes.fromhex('cb175601'), branch(0x1e05274,symbols['gb_ble_tail'],False), 'gb_ble_tail')
    # Stock BSS ends at 0x40b8; relocated code starts at 0x40c0. Reserve four padding bytes.
    require(app[0x12:0x1e] == bytes.fromhex('c1ffc01c0000c2fff8230000'), 'Startup BSS layout mismatch')
    require(app[0x72:0x78] == bytes.fromhex('c0ffc0400000'), 'RAM-code destination mismatch')
    put(0x1e00138, bytes.fromhex('c2fff8230000'), bytes.fromhex('c2fffc230000'), 'Zero reserved epoch word at 0x40b8; stop before RAM code')
    require(0x1cc0 + 0x23fc == 0x40bc < 0x40c0, 'Epoch overlaps RAM code')
    output.extend(b'\0' * (append - len(output)))
    output.extend(payload)
    output.extend(b'\0' * (-len(output) % 32))
    # Independently decode every changed instruction using the extended SLEIGH description.
    arch = pypcode.Arch('Jieli', str(ROOT/'q32s-analysis/processor/data/languages/JieLi.ldefs'))
    ctx = pypcode.Context(next(x for x in arch.languages if x.id == 'q32s:LE:32:default'))
    for patch in patches:
        addr = int(patch['address'], 16)
        instruction = ctx.disassemble(bytes.fromhex(patch['after']), addr, max_instructions=1).instructions[0]
        require(instruction.length == len(bytes.fromhex(patch['after'])), 'Patch instruction width changed')
        patch['decoded'] = instruction.mnem + ' ' + instruction.body
        if patch['purpose'] in symbols:
            require(instruction.mnem == ('goto' if patch['purpose'] == 'gb_ble_tail' else 'call') and int(instruction.body,16) == symbols[patch['purpose']], 'Hook target mismatch')
    changed = {i for i,(a,b) in enumerate(zip(app,output)) if a != b}
    allowed = {i for p in patches for i in range(int(p['offset'],16), int(p['offset'],16)+len(bytes.fromhex(p['before'])))}
    require(changed <= allowed, 'Unlisted original application change')
    return bytes(output), patches

def prepare():
    original = BACKUP.read_bytes()
    require((BACKUP.parent/'flash-pass2.bin').read_bytes() == original, 'Backup copies differ')
    stock = (OUT/'stock-app-device-layout.bin').read_bytes()
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
    require(min(sectors) >= 0x2000 and max(sectors)+4096 <= 0x34000, 'Update extent exceeds writer bounds')
    report = {'status':'WITHDRAWN after 2026-10-25 boot failure; install blocked; see docs/boot-failure.md', 'stock_sha256':STOCK_SHA, 'target_sha256':digest(custom), 'app_sha256':digest(patched), 'app_size':len(patched), 'payload_size':len(payload), 'changed_sectors':sectors, 'patches':patches, 'state':{'task_stack_extra':40,'task_stack_request_before':2048,'task_stack_request_after':2112,'epoch_address':'0x40b8','queue_capacity':16}, 'preserved':'All bytes outside used active application area; config and P11 content retained, file headers/offsets updated'}
    DEST.mkdir(exist_ok=True)
    (DEST/'app.bin').write_bytes(patched)
    (DEST/'custom-device-layout.bin').write_bytes(custom)
    (DEST/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT.parent/'docs/evidence/custom-image.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Custom candidate: {len(payload)}-byte payload, {len(sectors)} changed sectors, SHA256 {digest(custom)}')
    return stock, custom, report
if __name__ == '__main__': prepare()
