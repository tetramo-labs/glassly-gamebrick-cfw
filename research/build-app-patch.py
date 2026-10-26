"""Build an unflashed, version-locked Q32S application patch.

Mirrors validated HID report payloads to existing vendor characteristic AE42.
This only produces app.bin and a manifest; it does NOT make a flashable UFW.
"""
from pathlib import Path
import hashlib, json, struct
import pypcode
ROOT=Path(__file__).resolve().parent
BASE=0x1e00120
CALL_OFFSET=0x4128
ATT_SEND=0x1e034b4
EXPECTED='2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259'

def call(src,dst):
    delta=dst-(src+4)
    assert delta%2==0 and -(1<<22)<=delta<(1<<22)
    return struct.pack('<HH',0xf380|((delta>>17)&0x3f),(delta>>1)&0xffff)

def build():
    original=(ROOT/'unpacked/files/app.bin').read_bytes()
    assert hashlib.sha256(original).hexdigest()==EXPECTED, 'Unrecognized stock application'
    assert original[CALL_OFFSET:CALL_OFFSET+4]==call(BASE+CALL_OFFSET,ATT_SEND)
    # Exact stock GATT declaration: AE42 is a NOTIFY characteristic at handle 0x54.
    assert bytes.fromhex('0d0002005300032810540042ae08001000540042ae') in original
    # The original call sets its fifth argument (ATT_OP_AUTO_READ_CCC) to zero.
    assert original[0x4122:0x4128]==bytes.fromhex('03700b024308')
    offset=(len(original)+15)&~15
    stub=bytearray()
    def raw(h): stub.extend(bytes.fromhex(h))
    def invoke(): stub.extend(call(BASE+offset+len(stub),ATT_SEND))
    raw('7701 fe0b')       # save rets, r4-r7; reserve fifth argument
    raw('0408 1508 2608 3708')  # preserve connection, handle, data, length
    raw('0070 0802 4008')  # fifth argument = 0; restore connection
    invoke()              # original HID send, original handle/data/length
    raw('0508')           # preserve original return value in r5
    raw('4008 4175 6208 7308')  # connection, AE42 handle, original data, length
    invoke()              # mirror, ignored return value
    raw('5008 020a 5701')  # original return; restore stack and registers
    growth=(offset+len(stub)-len(original)+31)&~31
    patched=bytearray(original)+bytearray(growth)
    patched[offset:offset+len(stub)]=stub
    patched[CALL_OFFSET:CALL_OFFSET+4]=call(BASE+CALL_OFFSET,BASE+offset)
    assert growth==64
    assert patched[:CALL_OFFSET]==original[:CALL_OFFSET]
    assert patched[CALL_OFFSET+4:len(original)]==original[CALL_OFFSET+4:]
    lang=next(x for x in pypcode.Arch('Jieli',str(ROOT/'ghidra-jieli/data/languages/JieLi.ldefs')).languages if x.id.startswith('q32s:'))
    ctx=pypcode.Context(lang)
    decoded=ctx.disassemble(bytes(stub),BASE+offset).instructions
    assert sum(i.length for i in decoded)==len(stub)
    assert [i.body for i in decoded if i.mnem=='call']==[hex(ATT_SEND),hex(ATT_SEND)]
    branch=ctx.disassemble(bytes(patched[CALL_OFFSET:CALL_OFFSET+4]),BASE+CALL_OFFSET).instructions[0]
    assert branch.mnem=='call' and branch.body==hex(BASE+offset)
    listing='\n'.join(f'{i.addr.offset:08x}: {i.mnem:8} {i.body}' for i in decoded)+'\n'
    out=ROOT/'candidate';out.mkdir(exist_ok=True)
    (out/'app.experimental.bin').write_bytes(patched)
    (out/'mirror-stub.disasm.txt').write_text(listing)
    manifest={'status':'OFFLINE CANDIDATE; NOT HARDWARE TESTED; NOT A FLASHABLE UPDATE',
      'stock_app_sha256':EXPECTED,'patched_app_sha256':hashlib.sha256(patched).hexdigest(),
      'stock_app_size':len(original),'patched_app_size':len(patched),'growth':growth,
      'call_offset':hex(CALL_OFFSET),'stub_address':hex(BASE+offset),'stub_length':len(stub),
      'vendor_characteristic':'AE42','vendor_handle':'0x54','payload':'Unmodified HID report payload, without report ID; use C mode for initial tests',
      'preserved':'Original HID send occurs first; its return value is preserved; vendor send return ignored',
      'remaining':['Validate USB recovery/readback','Package and validate both UFW flash variants and integrity metadata','Hardware test HID and AE42 notifications','iOS background/lock test']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(listing);print(json.dumps(manifest,indent=2))
if __name__=='__main__': build()
