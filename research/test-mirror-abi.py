"""Exercise independently decoded stub instructions against a clobbering ATT mock.
This is an ABI regression check, not a CPU/firmware/hardware emulator.
"""
import random,re
from pathlib import Path
import pypcode
root=Path(__file__).resolve().parent
lang=next(x for x in pypcode.Arch('Jieli',str(root/'ghidra-jieli/data/languages/JieLi.ldefs')).languages if x.id.startswith('q32s:'))
ctx=pypcode.Context(lang)
app=(root/'candidate/app.experimental.bin').read_bytes()
ins=ctx.disassemble(app[0x308b0:0x308b0+42],0x1e309d0).instructions
rng=random.Random(1161)
for n in range(500):
    regs={f'r{i}':rng.getrandbits(32) for i in range(16)}
    regs.update(sp=0x10000,rets=0x12345678)
    initial=regs.copy();mem={};calls=[];results=[rng.choice([0,-1,12,13]),rng.choice([0,-1,12,13])]
    for i in ins:
        if i.mnem=='push':
            assert i.body=='{rets, 0x7}'
            for reg in ['rets','r4','r5','r6','r7']:
                regs['sp']-=4;mem[regs['sp']]=regs[reg]
        elif i.mnem=='pop':
            assert i.body=='{pc, 0x7}'
            for reg in ['r7','r6','r5','r4','pc']:
                regs[reg]=mem[regs['sp']];regs['sp']+=4
        elif i.mnem=='mov':
            dst,src=i.body.split(', ');regs[dst]=int(src[1:],0) if src.startswith('#') else regs[src]
        elif i.mnem=='add':
            dst,imm=i.body.split(', ');regs[dst]+=int(imm[1:],0)
        elif i.mnem=='sw':
            assert i.body=='r0, [sp + 0x0]';mem[regs['sp']]=regs['r0']
        elif i.mnem=='call':
            assert i.body=='0x1e034b4'
            calls.append(tuple(regs[f'r{k}'] for k in range(4))+(mem[regs['sp']],))
            for k in range(4):regs[f'r{k}']=rng.getrandbits(32)
            regs['r0']=results[len(calls)-1];regs['rets']=i.addr.offset+i.length
        else:raise AssertionError(i.mnem)
    assert calls==[(initial['r0'],initial['r1'],initial['r2'],initial['r3'],0),(initial['r0'],0x54,initial['r2'],initial['r3'],0)]
    assert regs['r0']==results[0]
    assert all(regs[r]==initial[r] for r in ['r4','r5','r6','r7','sp'])
    assert regs['pc']==initial['rets']
print('500 decoded-instruction ABI cases passed: original and vendor arguments, return value, callee-saved registers, stack and return address')
