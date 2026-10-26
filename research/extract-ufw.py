from pathlib import Path
exec(open(str(Path(__file__).resolve().parent / 'inspect-ufw.py')).read().split("print('Header:'")[0])
out=Path(str(Path(__file__).resolve().parent / 'ufw-parts'));out.mkdir(exist_ok=True)
for i in range(struct.unpack_from('<H',h,8)[0]):
    off=64+i*80; e=bytearray(b[off:off+80]);jl_enc_cipher(e,0,80)
    typ,idx,crc,wa1,start,size,size2,extra,name=struct.unpack('<HHHHIII44s16s',e)
    name=name.split(b'\0')[0].decode();data=bytearray(b[start:start+size2])
    if jl_crc16(data[:size]) != crc:
        jl_enc_cipher(data,0,len(data))
        print(name,'decoded CRC',jl_crc16(data[:size])==crc)
    (out/name).write_bytes(data[:size])
