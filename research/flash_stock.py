#!/usr/bin/env python3
"""Install the OEM application or restore the original backup on this controller."""
import argparse,ctypes,hashlib,json,os,signal,struct,sys,time
from pathlib import Path
from stock_update import ROOT,BACKUP,ORIGINAL_SHA,OUT,require,digest
from jltech.crc import jl_crc16
SIZE=0x80000
SECTOR=4096
PAGE=256
TARGET_SHA='dfbaeffd4e4cb2c940481cab918b55e29c2eea47107e3214ed12af96b03e8465'
LOADER_SHA='faa1b519a3ff1b082f11ccafac8c73d31150161ac972ef9f1934002bcbb8df4f'

class Transport:
    def __init__(self,native,sectors):
        self.native=native;self.sectors=frozenset(sectors);self.tag=0;self.writes_enabled=False
    def transfer(self,ep,data_or_size):
        if ep==1: data=bytes(data_or_size);buf=ctypes.create_string_buffer(data);size=len(data)
        else:size=data_or_size;buf=ctypes.create_string_buffer(size)
        count=self.native.gb_transfer(ep,buf,size,10000)
        require(count>=0,self.native.gb_error().decode())
        require(count==size,f'Short USB transfer: {count}/{size}')
        return buf.raw[:count]
    def execute(self,cdb,out=None,n=0):
        require(0<len(cdb)<=16 and not(out is not None and n),'Invalid command')
        op=int.from_bytes(cdb[:2],'big');addr=int.from_bytes(cdb[2:6],'big')
        if cdb==bytes.fromhex('120000002400'):require(out is None and n==36,'Invalid inquiry')
        elif op in (0xfb01,0xfb04):
            require(self.writes_enabled,'Writes have not been authorized by full-image checks')
            require(addr//SECTOR*SECTOR in self.sectors,'Write outside selected sectors')
            if op==0xfb01:require(addr%SECTOR==0 and out is None and n==16,'Invalid sector erase')
            else:require(out is not None and len(out)==PAGE and addr%PAGE==0 and int.from_bytes(cdb[6:8],'big')==PAGE,'Invalid flash page')
        elif op in (0xfb06,0xfd07):
            length=len(out) if out is not None else n
            require(0x2000<=addr and addr+length<=0x2000+23040 and length<=512,'Invalid loader RAM access')
            require(int.from_bytes(cdb[6:8],'big')==length,'Invalid RAM length')
            require((op==0xfb06 and out is not None) or (op==0xfd07 and out is None),'Wrong RAM direction')
        elif op==0xfb08:require(cdb[2:8]==bytes.fromhex('000020000001') and out is None and n==16,'Invalid RAM jump')
        elif op==0xfd05:require(0<=addr and addr+n<=SIZE and n==PAGE and out is None and int.from_bytes(cdb[6:8],'big')==n,'Invalid flash read')
        else:require(op in (0xfc0a,0xfc0b,0xfc14) and out is None and n==16,'Forbidden command')
        self.tag+=1;size=len(out) if out is not None else n
        cbw=struct.pack('<4sIIBBB16s',b'USBC',self.tag,size,0x80 if n else 0,0,len(cdb),cdb)
        self.transfer(1,cbw)
        data=b''
        if out is not None:self.transfer(1,out)
        elif n:data=self.transfer(0x81,n)
        csw=self.transfer(0x81,13)
        require(struct.unpack('<4sIIB',csw)==(b'USBS',self.tag,0,0),'Failed USB command status')
        return data
    def command(self,op,args=b'',out=None,n=16):
        return self.execute((op.to_bytes(2,'big')+args).ljust(16,b'\xff'),out,n=0 if out is not None else n)
    def reply(self,op,args=b''):
        data=self.command(op,args)
        require(data[:2]==op.to_bytes(2,'big'),'Unexpected command response')
        return data[2:]
    def initialize(self):
        inquiry=self.execute(bytes.fromhex('120000002400'),n=36)
        require(inquiry[8:16].decode().strip()=='BD19' and inquiry[16:32].decode().strip()=='UBOOT1.00','Wrong controller bootloader')
        loader=(ROOT/'jl-uboot-tool/data/loaderblobs/usb/bd19loader.bin').read_bytes()
        require(len(loader)==23040 and digest(loader)==LOADER_SHA,'RAM loader hash mismatch')
        print('BD19 identity confirmed. Loading and verifying RAM loader.',flush=True)
        for off in range(0,len(loader),512):
            block=loader[off:off+512];addr=0x2000+off
            self.command(0xfb06,struct.pack('>IH',addr,len(block))+b'\0'+jl_crc16(block).to_bytes(2,'little'),out=block)
            require(self.command(0xfd07,struct.pack('>IH',addr,len(block)),n=len(block))==block,'RAM loader readback mismatch')
        self.reply(0xfb08,bytes.fromhex('000020000001'))
        online=self.reply(0xfc0a);fid=self.reply(0xfc0b);buf=self.reply(0xfc14)
        require(online[0]==3 and int.from_bytes(online[2:6],'little')==0xcd7113,'Wrong flash device')
        require(int.from_bytes(fid[:3],'big')==0xcd71,'Flash ID responses disagree')
        require(int.from_bytes(buf[:4],'big')>=PAGE,'Insufficient loader buffer')
    def read(self,addr,size):
        require(addr%PAGE==0 and size%PAGE==0,'Read must be page aligned')
        return b''.join(self.command(0xfd05,struct.pack('>IH',a,PAGE),n=PAGE) for a in range(addr,addr+size,PAGE))
    def erase(self,addr):self.reply(0xfb01,addr.to_bytes(4,'big'))
    def program(self,addr,data):self.command(0xfb04,struct.pack('>IH',addr,len(data))+b'\0'+jl_crc16(data).to_bytes(2,'little'),out=data)


def program_image(device,original,target,mode,before=None,save_before=None):
    require(len(original)==len(target)==SIZE,'Incorrect image size')
    sectors=[a for a in range(0,SIZE,SECTOR) if original[a:a+SECTOR]!=target[a:a+SECTOR]]
    require(sectors and min(sectors)>=0x2000 and max(sectors)+SECTOR<=0x34000,'Unexpected update extent')
    print('Reading all flash before allowing writes.',flush=True)
    current=device.read(0,SIZE) if before is None else before
    require(len(current)==SIZE,'Incomplete pre-write read')
    if save_before:save_before(current)
    desired=target if mode=='install' else original
    if current==desired:
        print('Already matches requested image; no writes needed.',flush=True);return {'writes':0,'sha256':digest(current)}
    if mode=='install':require(current==original,'Installed flash differs from the verified backup; no writes allowed')
    else:
        for a in range(0,SIZE,SECTOR):
            if a not in sectors:require(current[a:a+SECTOR]==original[a:a+SECTOR],f'Protected sector {a:#x} changed; refusing recovery on unidentified state')
    device.writes_enabled=True
    # Commit the active application header last. This is not atomic across power loss.
    ordered=sectors[1:]+sectors[:1];count=0
    for a in ordered:
        block=desired[a:a+SECTOR]
        if current[a:a+SECTOR]==block:continue
        require(device.read(a,SECTOR)==current[a:a+SECTOR],f'Sector {a:#x} changed since preflight')
        device.erase(a)
        require(device.read(a,SECTOR)==b'\xff'*SECTOR,f'Sector erase failed at {a:#x}')
        for off in range(0,SECTOR,PAGE):
            page=block[off:off+PAGE]
            if page!=b'\xff'*PAGE:device.program(a+off,page)
        require(device.read(a,SECTOR)==block,f'Sector verification failed at {a:#x}')
        count+=1;print(f'Verified sector {a:#07x} ({count}/{len(sectors)})',flush=True)
    final=device.read(0,SIZE)
    require(final==desired,'Full flash readback differs from intended image')
    return {'writes':count,'sha256':digest(final),'full_readback_verified':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['install','restore']);args=parser.parse_args()
    original=BACKUP.read_bytes();target=(OUT/'stock-app-device-layout.bin').read_bytes()
    require(digest(original)==ORIGINAL_SHA and (BACKUP.parent/'flash-pass2.bin').read_bytes()==original,'Original backup failed validation')
    require(digest(target)==TARGET_SHA,'Prepared update hash mismatch; rebuild and review before flashing')
    sectors=[a for a in range(0,SIZE,SECTOR) if original[a:a+SECTOR]!=target[a:a+SECTOR]]
    result=ROOT/('stock-flash-'+time.strftime('%Y%m%d-%H%M%S'));result.mkdir();owner=ROOT.stat().st_uid
    if os.geteuid()==0:os.chown(result,owner,-1)
    log=(result/'operation.log').open('w',buffering=1)
    class Tee:
        def __init__(self,stream):self.stream=stream
        def write(self,s):self.stream.write(s);log.write(s)
        def flush(self):self.stream.flush();log.flush()
    sys.stdout=Tee(sys.stdout);sys.stderr=Tee(sys.stderr)
    print('Output:',result,flush=True);print('Operation:',args.mode,flush=True)
    native=ctypes.CDLL(str(ROOT/'native-usb.dylib'));native.gb_error.restype=ctypes.c_char_p
    native.gb_transfer.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_int]
    signal.alarm(2100);deadline=time.monotonic()+1800;opened=False
    try:
        print('Waiting up to 30 minutes for update mode (Pairing+B for two seconds).',flush=True)
        while True:
            code=native.gb_open()
            if code==0:opened=True;break
            require(code==-2,native.gb_error().decode())
            require(time.monotonic()<deadline,'Timed out waiting for controller')
            time.sleep(0.25)
        transport=Transport(native,sectors);transport.initialize()
        # Flush the pre-write read to storage before any sector is erased.
        def save_before(data):
            with (result/'before.bin').open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        report=program_image(transport,original,target,args.mode,save_before=save_before)
        report.update(mode=args.mode,original_sha256=ORIGINAL_SHA,target_sha256=TARGET_SHA,hardware_functional_test='pending')
        (result/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print('FLASH VERIFIED:',report['sha256'],flush=True)
        print('Power-cycle the controller, then test all buttons and pairing.',flush=True)
    finally:
        if opened:native.gb_close()
        for p in result.iterdir():
            if os.geteuid()==0:os.chown(p,owner,-1)
if __name__=='__main__':main()
