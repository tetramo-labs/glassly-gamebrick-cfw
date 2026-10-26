"""Extend the isolated language using encodings checked with the official objdump."""
from pathlib import Path
import json,re
root=Path(__file__).resolve().parent
lang=root/'q32s-analysis/processor/data/languages'
# Register list semantics; save rets first, then ascending GPRs, restore in reverse.
s=['# Generated Q32S register-list stack semantics. See docs/q32s-decoder.md.']
for opcode,action,extra in [(0x100,'pop',None),(0x110,'pop','rets'),(0x150,'pop','pc'),(0x160,'push',None),(0x170,'push','rets')]:
 for n in range(16):
  regs=[f'r{i}' for i in (range(n,4) if n<4 else range(4,n+1))]
  display=', '.join(([extra] if extra else [])+list(reversed(regs)))
  order=([extra] if extra else [])+regs if action=='push' else list(reversed(regs))+([extra] if extra else [])
  semantic=' '.join(f'{action}({reg});' for reg in order)
  if extra=='pc':semantic+=' return [pc];'
  s.append(f':{action} "{{{display}}}" is group=0 & ins0012=0x{opcode+n:04x} {{ {semantic} }}')
for opcode,action in [(0x180,'pop'),(0x1c0,'push')]:
 for mask in range(1,64):
  regs=[name for i,name in enumerate(['reti','rete','retx','rets','sr4','psr']) if mask&(1<<i)]
  order=regs if action=='push' else list(reversed(regs))
  display=', '.join(reversed(regs))
  s.append(f':{action} "{{{display}}}" is group=0 & ins0012=0x{opcode+mask:04x} {{ '+ ' '.join(f'{action}({reg});' for reg in order)+' }')
s+=[':pop pc is group=0 & ins0012=0x0030 & pc { pop(pc); return [pc]; }',':push rets is group=0 & ins0012=0x0034 & rets { push(rets); }']
(lang/'q32s_ins_stack.sinc').write_text('\n'.join(s)+'\n')
s=[]
for code,name,operator in [(0x1df0,'lsl','<<'),(0x1df2,'lsr','>>'),(0x1df3,'qasr','s>>')]:
 s.append(f':{name} regE, regF, imm1923 is group=7 & ins0012=0x{code:x}; regE & regF & imm1923 {{ local n:4=imm1923; if (n != 0) goto <shift>; n=32; <shift> regE=regF {operator} n; }}')
for code,name,operator in [(0x1df8,'lsl','<<'),(0x1dfa,'lsr','>>'),(0x1dfb,'qasr','s>>')]:
 s.append(f':{name} regE, regF, regG is group=7 & ins0012=0x{code:x}; regE & regF & regG {{ regE=regF {operator} regG; }}')
s.append(':clz regE, regF is group=7 & ins0012=0x1de8; regE & regF { regE=lzcount(regF); }')
for cond,name,op in [(0,'jeq','=='),(1,'jne','!='),(2,'jcs','>='),(3,'jcc','<'),(8,'jhi','>'),(9,'jls','<='),(10,'jge','s>='),(11,'jlt','s<'),(12,'jgt','s>'),(13,'jle','s<=')]:
 s.append(f':{name} regE, "#"weirdimm, pcrel17m2 is group=7 & ins0012=0x{0x1f20+cond:x}; regE & weirdimm; pcrel17m2 {{ if (regE {op} weirdimm) goto pcrel17m2; }}')
(lang/'q32s_extensions.sinc').write_text('\n'.join(s)+'\n')
p=lang/'q32s.slaspec';p.write_text(p.read_text()+'\n@include "q32s_extensions.sinc"\n')
# Fix signed field extraction, which previously used the same shift on both sides.
p=lang/'q32s_ins_regfield.sinc';s=p.read_text();old='local lastbit:1 = 31 - imm1923 - imm0004;\n\tregE = (regF << lastbit) s>> lastbit;';new='local width:4 = imm0004;\n\tif (width != 0) goto <extract>; width=32;\n\t<extract> regE = (regF << (32 - imm1923 - width)) s>> (32 - width);';assert old in s;s=s.replace(old,new);p.write_text(s)
p=root/'q32s-analysis/processor-corrections.json';m=json.loads(p.read_text());m['corrections']+=['register-list and special-register stack semantics','32-bit register/immediate shifts','clz','48-bit comparisons with expanded immediate','signed field extraction'];m['limits']=['condition flags and uncommon instruction families remain incomplete','stack slot ordering follows the related PI32V2 module; no hardware register trace','function discovery heuristic; generated C is not ground truth'];p.write_text(json.dumps(m,indent=2)+'\n')

# Unsigned compare immediates are zero-extended; the upstream spec sign-extends them.
p=lang/'q32s.slaspec';s=p.read_text().replace('imm1627s = (0,11) signed','imm1627s = (0,11) signed\n\timm1627 = (0,11)');p.write_text(s)
p=lang/'q32s_ins_progflow.sinc';s=p.read_text()
for name in ['jcs','jcc','jhi','jls']:
 for signed,unsigned in [('imm0411s','imm0411'),('imm1627s','imm1627')]:
  s=re.sub(r'(:'+name+r'[^\n]*\n\{[^\n]*\})',lambda m:m[0].replace(signed,unsigned),s)
p.write_text(s)
