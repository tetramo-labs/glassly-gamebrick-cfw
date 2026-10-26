from pathlib import Path
exec(open(str(Path(__file__).resolve().parent / 'disasm.py')).read().split('if len(sys.argv)>1:')[0])
targets={'0x1e0420c':'hid_send','0x1e04250':'vendor_send','0x1e034b4':'att_send'}
for off in range(0,0x1d600,2):
    try:
        ins=c.disassemble(b[off:off+16],BASE+off,max_instructions=1).instructions[0]
        if ins.mnem in ['call','goto'] and ins.body in targets:
            print(hex(off),targets[ins.body],ins.mnem,ins.body)
    except Exception: pass
