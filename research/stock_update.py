"""Build a device-layout image containing the unmodified OEM application."""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'jl-misctools/firmware'))
from jltech.cipher import jl_sfc_cipher
from jltech.crc import jl_crc16
BACKUP=ROOT/'device-backup-20261022-233350/flash-pass1.bin'
ORIGINAL_SHA='9b7c57387ded72fadd162599cfb2b3797fb27e10759918d4e06f879740577cb3'
OEM_SHA='2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259'
BASE=0x2020
LIMIT=0x3e020
OUT=ROOT/'stock-update-prepared'

def require(ok,message):
    if not ok: raise RuntimeError(message)
def digest(data):return hashlib.sha256(data).hexdigest()
def entry(data,off):
    require(len(data)>=off+32,'Truncated entry')
    e=struct.unpack_from('<HHIIBBH16s',data,off)
    require(jl_crc16(data[off+2:off+32])==e[0],'Entry CRC mismatch')
    return e
def header_crc(data,off):struct.pack_into('<H',data,off,jl_crc16(data[off+2:off+32]))

def build(original,replacement):
    require(len(original)==0x80000 and digest(original)==ORIGINAL_SHA,'Wrong original backup')
    plain=bytearray(original)
    jl_sfc_cipher(plain,BASE,LIMIT-BASE,BASE,0x190d)
    area=entry(plain,BASE);app=entry(plain,BASE+32);cfg=entry(plain,BASE+64)
    require(area[2]==0x1e00120 and app[2:4]==(0x120,196224),'Unexpected application layout')
    require(app[-1].startswith(b'app.bin\0') and cfg[-1].startswith(b'cfg_tool.bin\0'),'Unexpected file table')
    p11=entry(plain,BASE+area[3]);used=area[3]+p11[3]
    require(p11[-1].startswith(b'p11_code.bin\0'),'Unexpected resource')
    region=plain[BASE:BASE+used]
    require(jl_crc16(region[32:area[3]])==area[1],'Application area CRC mismatch')
    require(jl_crc16(region[app[2]:app[2]+app[3]])==app[1],'Application CRC mismatch')
    require(cfg[2]==app[2]+app[3] and cfg[2]+cfg[3]==area[3],'Unexpected file gaps')
    require(jl_crc16(region[cfg[2]:cfg[2]+cfg[3]])==cfg[1],'Configuration CRC mismatch')
    require(jl_crc16(region[area[3]+32:used])==p11[1],'P11 CRC mismatch')
    growth=len(replacement)-app[3]
    require(0<=growth and BASE+used+growth<LIMIT,'Update exceeds active area')
    updated=region[:app[2]]+replacement+region[app[2]+app[3]:]
    struct.pack_into('<H',updated,34,jl_crc16(replacement))
    struct.pack_into('<I',updated,40,len(replacement));header_crc(updated,32)
    struct.pack_into('<I',updated,68,cfg[2]+growth);header_crc(updated,64)
    struct.pack_into('<I',updated,8,area[3]+growth)
    struct.pack_into('<H',updated,2,jl_crc16(updated[32:area[3]+growth]));header_crc(updated,0)
    require(updated[96:app[2]]==region[96:app[2]],'Partition entries changed')
    require(updated[cfg[2]+growth:]==region[cfg[2]:],'Config or P11 changed')
    output=bytearray(original);output[BASE:BASE+len(updated)]=updated
    jl_sfc_cipher(output,BASE,len(updated),BASE,0x190d)
    require(output[:BASE]==original[:BASE] and output[BASE+len(updated):]==original[BASE+len(updated):],'Unrelated bytes changed')
    return bytes(output)

def prepare():
    original=BACKUP.read_bytes()
    require((BACKUP.parent/'flash-pass2.bin').read_bytes()==original,'Backup copies differ')
    installed=(BACKUP.parent/'unpacked/files/app.bin').read_bytes()
    require(build(original,installed)==original,'Original-image roundtrip failed')
    replacement=(ROOT/'unpacked/files/app.bin').read_bytes()
    require(digest(replacement)==OEM_SHA,'OEM application hash mismatch')
    for name in ('cfg_tool.bin','p11_code.bin'):
        require((ROOT/'unpacked/files'/name).read_bytes()==(BACKUP.parent/'unpacked/files'/name).read_bytes(),name+' differs')
    for name in ('uboot.boot','isd_config.ini'):
        require((ROOT/'unpacked/top'/name).read_bytes()==(BACKUP.parent/'unpacked/top'/name).read_bytes(),name+' differs')
    output=build(original,replacement)
    sectors=[a for a in range(0,len(original),4096) if original[a:a+4096]!=output[a:a+4096]]
    OUT.mkdir(exist_ok=True)
    (OUT/'stock-app-device-layout.bin').write_bytes(output)
    report={'status':'PREPARED; NOT FLASHED; hardware compatibility untested','original_sha256':ORIGINAL_SHA,'target_sha256':digest(output),'application_sha256':OEM_SHA,'application_bytes':len(replacement),'flash_bytes':len(output),'sector_bytes':4096,'changed_sectors':sectors,'changed_sector_count':len(sectors),'first_changed_byte':next(i for i,(a,b) in enumerate(zip(original,output)) if a!=b),'last_changed_byte':max(i for i,(a,b) in enumerate(zip(original,output)) if a!=b),'preserved':'Bootloader, top-level partition map, inactive slot, VM, Bluetooth data, user data, key/MAC, config and P11 payloads','method':'Unmodified official application; installed file table retained with updated sizes, offsets and CRCs; P11 relocated within active area'}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return original,output,report
if __name__=='__main__':prepare()
