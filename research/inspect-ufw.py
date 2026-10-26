import sys, struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent / 'jl-misctools/firmware'))
from jltech.cipher import jl_enc_cipher
from jltech.crc import jl_crc16
b=Path(str(Path(__file__).resolve().parent / 'stock.ufw')).read_bytes()
h=bytearray(b[:64]); jl_enc_cipher(h,0,64)
print('Header:',struct.unpack('<HHIHHI48s',h))
for i in range(struct.unpack_from('<H',h,8)[0]):
    off=64+i*80; e=bytearray(b[off:off+80]);jl_enc_cipher(e,0,80)
    typ,idx,crc,wa1,start,size,size2,extra,name=struct.unpack('<HHHHIII44s16s',e)
    print(dict(type=typ,index=idx,crc=hex(crc),offset=hex(start),size=size,size2=size2,extra=extra.hex(),name=name,crc_matches=jl_crc16(b[start:start+size])==crc))
    if typ==0: Path(str(Path(__file__).resolve().parent / 'flash-original.bin')).write_bytes(b[start:start+size])
