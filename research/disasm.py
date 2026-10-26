from pathlib import Path
import pypcode, struct, sys
BASE=0x1e00120
b=Path(str(Path(__file__).resolve().parent / 'unpacked/files/app.bin')).read_bytes()
a=pypcode.Arch('Jieli',str(Path(__file__).resolve().parent / 'ghidra-jieli/data/languages/JieLi.ldefs'))
c=pypcode.Context(next(x for x in a.languages if x.id.startswith('q32s:')))
if len(sys.argv)>1:
    start=int(sys.argv[1],0); end=int(sys.argv[2],0) if len(sys.argv)>2 else start+128
    off=start
    while off<end:
        try:
            ins=c.disassemble(b[off:off+16],BASE+off,max_instructions=1).instructions[0]
            print(f'{off:06x} {ins.addr.offset:08x}: {b[off:off+ins.length].hex():12} {ins.mnem:8} {ins.body}')
            off+=ins.length
        except Exception as e:
            print(f'{off:06x}: {b[off:off+2].hex()} unknown')
            off+=2
else:
    for needle in [b'report_id %d,err!!!',b'write_callback, handle',b'IINE_keyboard',b'get_mouse',b'ret_mouse']:
        off=b.find(needle)
        print(needle,hex(off),hex(BASE+off))
        addr=struct.pack('<I',BASE+off)
        hits=[i for i in range(len(b)) if b.startswith(addr,i)]
        print('references', [hex(h) for h in hits])
