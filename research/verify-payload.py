"""Check the linked development component; this does not approve an image for flashing."""
from pathlib import Path
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'research/q32s-analysis'
APP_SHA = '2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

app = (ROOT / 'research/unpacked/files/app.bin').read_bytes()
require(sha(app) == APP_SHA, 'Unexpected stock application')
require(app[0xf074:0xf078] == bytes.fromhex('bf f3 3c ee'), 'Task call bytes changed')
elf = (OUT / 'vendor-payload.elf').read_bytes()
require(elf[:7] == b'\x7fELF\x01\x01\x01', 'Expected ELF32 little-endian')
header = struct.unpack_from('<HHIIIIIHHHHHH', elf, 16)
kind, machine, _, entry, _, shoff, _, _, _, _, shsize, shnum, stridx = header
require(kind == 2 and machine == 242, 'Expected Q32S executable')
require(entry == 0x1e309d0 and shsize == 40, 'Unexpected entry or section layout')
sections = [struct.unpack_from('<IIIIIIIIII', elf, shoff + i * shsize) for i in range(shnum)]
strings = sections[stridx]
names = elf[strings[4]:strings[4] + strings[5]]
by_name = {}
for section in sections:
    name = names[section[0]:].split(b'\0', 1)[0].decode()
    by_name[name] = section
    require(not (section[1] in (4, 9) and section[5]), 'Unresolved relocations')
    require(not (section[2] & 2 and name != '.text' and section[5]), 'Unexpected allocated section')
text = by_name['.text']
require(text[3] == entry and 0 < text[5] < 0x1000, 'Unexpected text placement/size')
symbols = {}
for section in sections:
    if section[1] != 2:
        continue
    st = sections[section[6]]
    strings = elf[st[4]:st[4] + st[5]]
    for off in range(section[4], section[4] + section[5], section[9]):
        name, value, size, info, other, index = struct.unpack_from('<IIIBBH', elf, off)
        name = strings[name:].split(b'\0', 1)[0].decode()
        require(not name or index != 0, 'Undefined symbol: ' + name)
        if name.startswith('gb_'):
            symbols[name] = hex(value)
for name in ('gb_task_entry', 'gb_task_tick', 'gb_tick', 'gb_poll', 'gb_ccc_changed', 'gb_ble_changed'):
    require(name in symbols, 'Missing hook: ' + name)
payload = (OUT / 'vendor-payload.bin').read_bytes()
require(payload == elf[text[4]:text[4] + text[5]], 'Binary differs from ELF text')
manifest = {
    'status': 'linked task/CCC/lifecycle hooks; requires verified image packaging and hardware tests',
    'application_sha256': APP_SHA,
    'entry': hex(entry), 'symbols': symbols,
    'payload_size': len(payload),
    'payload_sha256': sha(payload),
    'elf_sha256': sha(elf),
    'candidate_task_call': {'address': '0x01e0f194', 'file_offset': '0xf074', 'bytes': 'bff33cee', 'target': '0x01e0ce10'},
    'stock_symbols': {'gb_stock_ccc': '0x01e041b6', 'gb_stock_att': '0x01e034b4', 'gb_stock_handler': '0x01e0ce10', 'gb_stock_set_ccc': '0x01e14114', 'gb_stock_ble_event': '0x01e0520c'},
    'sources': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted((ROOT / 'firmware').iterdir()) if p.is_file()},
    'checks': ['exact stock application and candidate call bytes', 'Q32S ELF32 executable and entry', 'no relocation sections or extra allocated data', 'raw payload equals linked text'],
}
(ROOT / 'docs/evidence/q32s-payload.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Payload verified: {len(payload)} bytes, SHA256 {sha(payload)}. Component only; validate packaged image separately.')
