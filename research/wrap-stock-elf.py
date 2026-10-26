"""Wrap stock bytes in an analysis-only ELF; never a flashable image."""
from pathlib import Path
import struct,hashlib
r=Path(__file__).resolve().parent
b=(r/'unpacked/files/app.bin').read_bytes()
assert hashlib.sha256(b).hexdigest()=='2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259'
sections=[('.text',0x1e00120,b,6),('.ram_code',0x40c0,b[0x2eb08:0x30890],6)]
names=b'\0'+b'\0'.join(s[0].encode() for s in sections)+b'\0.shstrtab\0'
body=bytearray(52);headers=[bytes(40)]
for name,addr,data,flags in sections:
 body.extend(bytes((-len(body))%4));off=len(body);body.extend(data)
 headers.append(struct.pack('<10I',names.index(name.encode()),1,flags,addr,off,len(data),0,0,2,0))
off=len(body);body.extend(names);headers.append(struct.pack('<10I',names.index(b'.shstrtab'),3,0,0,off,len(names),0,0,1,0))
body.extend(bytes((-len(body))%4));shoff=len(body);body.extend(b''.join(headers))
body[:52]=struct.pack('<16sHHIIIIIHHHHHH',b'\x7fELF\x01\x01\x01'+bytes(9),2,242,1,0x1e00120,0,shoff,0,52,0,0,40,len(headers),len(headers)-1)
(r/'q32s-analysis/stock.analysis.elf').write_bytes(body)
