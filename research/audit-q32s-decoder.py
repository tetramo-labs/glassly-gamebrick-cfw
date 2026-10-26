"""Compare previous Ghidra failure sites against the official disassembler."""
from pathlib import Path
import re,json,pypcode
r=Path(__file__).resolve().parent;b=(r/'unpacked/files/app.bin').read_bytes()
a=pypcode.Arch('Jieli',str(r/'q32s-analysis/processor/data/languages/JieLi.ldefs'))
c=pypcode.Context(next(x for x in a.languages if x.id=='q32s:LE:32:default'))
vendor={}
for line in (r/'q32s-analysis/vendor-stock.asm').read_text().splitlines():
 m=re.match(r'^\s*([a-f0-9]+):\s+((?:[a-f0-9]{2} )+)\s+(.+)$',line)
 if m:vendor[int(m[1],16)]=(bytes.fromhex(m[2]),m[3])
old=json.loads((r.parent/'docs/evidence/q32s-decoder-baseline.json').read_text())
rows=[]
for addr in old['failure_addresses']:
 addr=int(addr,16);off=addr-0x1e00120 if addr>=0x1e00120 else addr-0x40c0+0x2eb08
 row={'address':hex(addr),'bytes':b[off:off+6].hex()}
 try:
  i=c.disassemble(b[off:off+16],addr,max_instructions=1).instructions[0]
  row['decoded']=i.mnem+' '+i.body
  if addr in vendor:
   raw,text=vendor[addr];row['vendor']=text;row['length_matches']=i.length==len(raw)
  else:row['vendor']='No matching boundary in linear vendor listing'
 except pypcode.BadDataError:row['decoded']=None
 rows.append(row)
out={'previous_failure_count':len(rows),'now_decoded':sum(x['decoded'] is not None for x in rows),'length_mismatches':[x['address'] for x in rows if x.get('length_matches') is False],'sites':rows}
(r.parent/'docs/evidence/q32s-decoder-audit.json').write_text(json.dumps(out,indent=2)+'\n')
print({k:v for k,v in out.items() if k!='sites'})
