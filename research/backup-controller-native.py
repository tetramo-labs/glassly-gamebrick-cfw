#!/usr/bin/env python3
"""Back up the IINE controller. No erase, flash-program or fuse commands.
Only RAM loader writes/jump, inquiry, identity and flash reads are allowed.
Transport adapted from USB Bulk-Only spec; Jieli commands from jl-uboot-tool.
"""
import ctypes, hashlib, json, os, signal, struct, sys, time
from pathlib import Path
import usb.core, usb.util, usb.backend.libusb1
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'jl-uboot-tool'))
from jltech.crc import jl_crc16
LOADER=ROOT/'jl-uboot-tool/data/loaderblobs/usb/bd19loader.bin'

class BOT:
    def __init__(self, dev): self.dev,self.tag=dev,0
    def execute(self,cdb,out=None,n=0):
        # A deliberately restricted transport: cannot erase/program flash/fuses.
        op=bytes(cdb[:2])
        assert cdb[0]==0x12 or op in (b'\xfb\x06',b'\xfb\x08',b'\xfd\x07',b'\xfd\x05',b'\xfc\x09',b'\xfc\x0a',b'\xfc\x0b',b'\xfc\x14',b'\xfc\x15',b'\xfc\x16')
        assert 1<=len(cdb)<=16 and not(out is not None and n)
        if op==b'\xfb\x06':
            addr=int.from_bytes(cdb[2:6],'big')
            assert out is not None and 0x2000<=addr and addr+len(out)<=0x2000+LOADER.stat().st_size
        if op==b'\xfb\x08': assert cdb[2:8]==bytes.fromhex('000020000001')
        self.tag+=1
        size=len(out) if out is not None else n
        cbw=struct.pack('<4sIIBBB16s',b'USBC',self.tag,size,0x80 if n else 0,0,len(cdb),cdb)
        assert self.dev.write(1,cbw,timeout=3000)==31
        data=b''
        if out is not None:
            assert self.dev.write(1,out,timeout=3000)==len(out)
        elif n:
            data=bytes(self.dev.read(0x81,n,timeout=5000))
        csw=bytes(self.dev.read(0x81,13,timeout=5000))
        assert len(csw)==13,('CSW size',csw.hex())
        sig,tag,residue,status=struct.unpack('<4sIIB',csw)
        assert (sig,tag,residue,status)==(b'USBS',self.tag,0,0),('CSW error',csw.hex())
        assert len(data)==n,('Short data',len(data),n)
        return data
    def command(self,op,args=b'',out=None,n=16):
        cdb=(op.to_bytes(2,'big')+args).ljust(16,b'\xff')
        return self.execute(cdb,out=out,n=0 if out is not None else n)
    def response(self,op):
        data=self.command(op)
        assert data[:2]==op.to_bytes(2,'big'),('Reply mismatch',hex(op),data.hex())
        return data[2:]

def main():
    result=ROOT/('device-backup-'+time.strftime('%Y%m%d-%H%M%S'))
    result.mkdir()
    owner=ROOT.stat().st_uid
    if os.geteuid()==0: os.chown(result,owner,-1)
    log=(result/'backup.log').open('w',buffering=1)
    class Tee:
        def __init__(self, stream): self.stream=stream
        def write(self,s): self.stream.write(s); log.write(s)
        def flush(self): self.stream.flush(); log.flush()
    sys.stdout=Tee(sys.stdout); sys.stderr=Tee(sys.stderr)
    print('Output:',result,flush=True)
    signal.alarm(2100)
    print('Waiting up to 30 minutes for controller update mode',flush=True)
    deadline=time.monotonic()+1800
    native=ctypes.CDLL(str(ROOT/'native-usb.dylib'))
    native.gb_error.restype=ctypes.c_char_p
    native.gb_transfer.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_int]
    class NativeDevice:
        def write(self,ep,data,timeout):
            buf=ctypes.create_string_buffer(bytes(data))
            count=native.gb_transfer(ep,buf,len(data),timeout)
            if count<0: raise RuntimeError(native.gb_error().decode())
            return count
        def read(self,ep,n,timeout):
            buf=ctypes.create_string_buffer(n)
            count=native.gb_transfer(ep,buf,n,timeout)
            if count<0: raise RuntimeError(native.gb_error().decode())
            return buf.raw[:count]
    while True:
        opened=native.gb_open()
        if opened==0: break
        if opened!=-2: raise RuntimeError(native.gb_error().decode())
        if time.monotonic()>deadline: raise RuntimeError('Controller did not enter update mode within 30 minutes')
        time.sleep(0.25)
    dev=NativeDevice()
    print('Native USB capture and bulk endpoints opened',flush=True)
    try:
        bot=BOT(dev)
        inquiry=bot.execute(bytes.fromhex('120000002400'),n=36)
        vendor=inquiry[8:16].decode('ascii').strip(); product=inquiry[16:32].decode('ascii').strip()
        print('SCSI identity:',repr(vendor),repr(product),inquiry.hex(),flush=True)
        (result/'inquiry.bin').write_bytes(inquiry)
        if (vendor,product)!=('BD19','UBOOT1.00'):
            raise RuntimeError('Identity does not match BD19 ROM; stopping without loading code')
        encoded=LOADER.read_bytes()
        print('BD19 RAM loader SHA256:',hashlib.sha256(encoded).hexdigest(),flush=True)
        print('Upload and verify RAM only; flash remains untouched',flush=True)
        for off in range(0,len(encoded),512):
            block=encoded[off:off+512]; addr=0x2000+off
            args=struct.pack('>IH',addr,len(block))+b'\0'+jl_crc16(block).to_bytes(2,'little')
            bot.command(0xfb06,args,out=block)
            check=bot.command(0xfd07,struct.pack('>IH',addr,len(block)),n=len(block))
            if check!=block: raise RuntimeError(f'RAM verification failed at {addr:#x}; not executing')
        print('RAM loader verified; start with SPI NOR argument 1',flush=True)
        reply=bot.command(0xfb08,bytes.fromhex('000020000001'))
        assert reply[:2]==b'\xfb\x08',reply.hex()
        metadata={'inquiry':inquiry.hex(),'vendor':vendor,'product':product,'loader_sha256':hashlib.sha256(encoded).hexdigest()}
        for name,op in [('online',0xfc0a),('flash_id',0xfc0b),('buffer_size',0xfc14)]:
            data=bot.response(op); metadata[name]=data.hex(); print(name,data.hex(),flush=True)
        # FC0A holds the complete JEDEC ID as a little-endian uint32.
        # FC0B returns only bits 31..8, omitting the density byte.
        online=bytes.fromhex(metadata['online'])
        if online[0]!=3: raise RuntimeError(f'Expected SPI0 NOR, got {online[0]:#x}')
        jedec=int.from_bytes(online[2:6],'little')
        shifted_id=int.from_bytes(bytes.fromhex(metadata['flash_id'])[:3],'big')
        if shifted_id!=(jedec>>8): raise RuntimeError('Flash ID responses disagree')
        if not 0<jedec<=0xffffff: raise RuntimeError(f'Invalid JEDEC ID: {jedec:#x}')
        exponent=jedec & 0xff
        if not 16<=exponent<=24: raise RuntimeError(f'Unrecognized flash density: {jedec:06x}')
        size=1<<exponent
        metadata.update(jedec_id=f'{jedec:06x}',size=size)
        (result/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print(f'JEDEC ID: {jedec:06x}',flush=True)
        blocksize=int.from_bytes(bytes.fromhex(metadata['buffer_size'])[:4],'big')
        if not 16<=blocksize<=65535: raise RuntimeError(f'Invalid loader buffer size {blocksize}')
        blocksize=min(blocksize,256)
        print('Flash size:',size,'bytes; read block:',blocksize,flush=True)
        hashes=[]
        for passno in (1,2):
            dest=result/f'flash-pass{passno}.bin'
            with dest.open('wb') as f:
                for addr in range(0,size,blocksize):
                    count=min(blocksize,size-addr)
                    block=bot.command(0xfd05,struct.pack('>IH',addr,count),n=count)
                    f.write(block)
                    if addr%65536==0: print(f'Pass {passno}: {addr:#x}/{size:#x}',flush=True)
            image=dest.read_bytes()
            if len(set(image))<8: raise RuntimeError('Readback lacks plausible firmware data')
            hashes.append(hashlib.sha256(image).hexdigest())
            print('SHA256',passno,hashes[-1],flush=True)
        if hashes[0]!=hashes[1]: raise RuntimeError('Backups differ; do not flash')
        metadata.update(size=size,sha256=hashes[0],passes_match=True,flash_modified=False)
        (result/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print('BACKUP COMPLETE. Two identical reads. No flash writes.',flush=True)
    finally:
        native.gb_close()
        for p in result.iterdir():
            if os.geteuid()==0: os.chown(p,owner,-1)

if __name__=='__main__': main()
