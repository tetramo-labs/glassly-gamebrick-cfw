"""Repack both stock flash layouts offline, preserving flash/partition sizes.
Produces raw experimental images, NOT a complete UFW or a flashing command.
"""
from pathlib import Path
import hashlib,struct,sys,json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'jl-misctools/firmware'))
from jltech.cipher import jl_enc_cipher,jl_sfc_cipher
from jltech.crc import jl_crc16
from jltech.chipkeybin import chipkeybin_decode

def entry(data, off):
    h=bytes(data[off:off+32])
    assert len(h)==32 and jl_crc16(h[2:])==struct.unpack_from('<H',h)[0], 'Header CRC'
    return struct.unpack('<HHIIBBH16s',h)

def fix_header(data, off):
    struct.pack_into('<H',data,off,jl_crc16(data[off+2:off+32]))

def patch_flash(raw,replacement):
    original=(ROOT/'unpacked/files/app.bin').read_bytes()
    base=key=None
    for off in range(32,160,32):
        h=bytearray(raw[off:off+32]);jl_enc_cipher(h,0,32)
        e=entry(h,0);name=e[-1].split(b'\0')[0]
        if name==b'app_dir_head': base=e[2]
        if name==b'isd_config.ini':
            ck=raw[e[2]:e[2]+32]
            assert jl_crc16(ck)==struct.unpack_from('<H',raw,e[2]+32)[0]
            key=chipkeybin_decode(ck)
    assert base in [0x1400,0x2000] and key==0x190d
    first=bytearray(raw[base:base+32]);jl_sfc_cipher(first,0,32,0,key)
    area=entry(first,0);area_size=area[3]
    region=bytearray(raw[base:])
    # Locate and decode the next (p11) header with the correct stream offset.
    tmp=bytearray(raw);jl_sfc_cipher(tmp,base,((area_size+32+31)//32)*32,base,key)
    p11=entry(tmp,base+area_size)
    assert p11[-1].split(b'\0')[0]==b'p11_code.bin'
    used=area_size+p11[3]
    plain=bytearray(raw);jl_sfc_cipher(plain,base,used,base,key)
    region=plain[base:base+used]
    area=entry(region,0);app=entry(region,32);cfg=entry(region,64)
    assert app[-1].split(b'\0')[0]==b'app.bin' and cfg[-1].split(b'\0')[0]==b'cfg_tool.bin'
    assert jl_crc16(region[32:area_size])==area[1]
    assert region[app[2]:app[2]+app[3]]==original
    assert jl_crc16(original)==app[1]
    cfg_bytes=bytes(region[cfg[2]:cfg[2]+cfg[3]])
    assert jl_crc16(cfg_bytes)==cfg[1]
    assert jl_crc16(region[area_size+32:used])==p11[1]
    growth=len(replacement)-len(original)
    assert growth in [0,64] and base+used+growth<=len(raw)
    # Refuse relocation if the app has direct pointers into the moved resources.
    lo=0x1e00120+len(original);hi=0x1e00000+used
    assert not any(lo<=struct.unpack_from('<I',original,i)[0]<hi for i in range(0,len(original)-3,2))
    region=region[:app[2]]+replacement+region[app[2]+app[3]:]
    struct.pack_into('<H',region,34,jl_crc16(replacement))
    struct.pack_into('<I',region,40,len(replacement));fix_header(region,32)
    struct.pack_into('<I',region,68,cfg[2]+growth);fix_header(region,64)
    struct.pack_into('<I',region,8,area_size+growth)
    struct.pack_into('<H',region,2,jl_crc16(region[32:area_size+growth]));fix_header(region,0)
    assert region[cfg[2]+growth:cfg[2]+growth+cfg[3]]==cfg_bytes
    assert region[area_size+growth:]==plain[base+area_size:base+used]
    out=bytearray(raw);out[base:base+len(region)]=region
    jl_sfc_cipher(out,base,len(region),base,key)
    assert len(out)==len(raw) and out[:base]==raw[:base] and out[base+len(region):]==raw[base+len(region):]
    return bytes(out)

original=(ROOT/'unpacked/files/app.bin').read_bytes()
replacement=(ROOT/'candidate/app.experimental.bin').read_bytes()
report=[]
for name in ['flash.bin','flash2.bin']:
    raw=(ROOT/'ufw-parts'/name).read_bytes()
    assert patch_flash(raw,original)==raw,'Byte-exact roundtrip failed'
    changed=patch_flash(raw,replacement)
    dest=ROOT/'candidate'/name.replace('.bin','.experimental.bin')
    dest.write_bytes(changed)
    report.append({'layout':name,'size':len(raw),'stock_sha256':hashlib.sha256(raw).hexdigest(),'patched_sha256':hashlib.sha256(changed).hexdigest(),'roundtrip':'byte-exact','bootloader':'unchanged','partition_boundaries':'unchanged','status':'OFFLINE ONLY; NOT FLASHED'})
(ROOT/'candidate/flash-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
