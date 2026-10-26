"""Offline NOR fault-injection and transport guard tests; no hardware access."""
import contextlib,io,struct
from flash_stock import Transport,program_image,SIZE,SECTOR,PAGE,TARGET_SHA
from stock_update import BACKUP,OUT,digest,build,ROOT
original=BACKUP.read_bytes();target=(OUT/'stock-app-device-layout.bin').read_bytes()
sectors={a for a in range(0,SIZE,SECTOR) if original[a:a+SECTOR]!=target[a:a+SECTOR]}
class NOR:
    def __init__(self,data,fail_page=None,bad_erase=False):
        self.data=bytearray(data);self.writes_enabled=False;self.erased=[];self.pages=0;self.fail_page=fail_page;self.bad_erase=bad_erase
    def read(self,a,n):return bytes(self.data[a:a+n])
    def erase(self,a):
        assert self.writes_enabled and a in sectors and a%SECTOR==0
        self.erased.append(a)
        if not self.bad_erase:self.data[a:a+SECTOR]=b'\xff'*SECTOR
    def program(self,a,b):
        assert self.writes_enabled and a//SECTOR*SECTOR in sectors and len(b)==PAGE and a%PAGE==0
        self.pages+=1
        if self.pages==self.fail_page:raise RuntimeError('Simulated disconnect during write')
        assert all((x&y)==y for x,y in zip(self.data[a:a+PAGE],b))
        self.data[a:a+PAGE]=b

def fails(fn):
    try:fn()
    except RuntimeError:return
    raise AssertionError('Expected rejection')

with contextlib.redirect_stdout(io.StringIO()):
    d=NOR(original);report=program_image(d,original,target,'install')
    assert bytes(d.data)==target and report['sha256']==TARGET_SHA
    assert d.erased[-1]==min(sectors) and set(d.erased)==sectors
    again=program_image(d,original,target,'install');assert again['writes']==0
    restored=program_image(d,original,target,'restore');assert bytes(d.data)==original
    broken=NOR(original,fail_page=4)
    fails(lambda:program_image(broken,original,target,'install'))
    assert broken.data[:0x2000]==original[:0x2000] and broken.data[0x34000:]==original[0x34000:]
    broken.fail_page=None;program_image(broken,original,target,'restore');assert bytes(broken.data)==original
    corrupt=bytearray(original);corrupt[0x7f100]^=1
    for mode in ('install','restore'):
        wrong=NOR(corrupt);fails(lambda:program_image(wrong,original,target,mode));assert not wrong.erased
    bad=NOR(original,bad_erase=True);fails(lambda:program_image(bad,original,target,'install'));assert bad.pages==0
    mutated=NOR(original)
    fails(lambda:program_image(mutated,original,target,'install',save_before=lambda _: (_ for _ in ()).throw(RuntimeError('Backup storage unavailable'))))
    assert not mutated.erased
# Validation must reject before even calling the native USB API.
class NeverUSB:
    def __getattr__(self,name):raise AssertionError('USB should not be reached')
t=Transport(NeverUSB(),sectors)
for op in (0xfb00,0xfb02,0xfc12,0xfc0c):fails(lambda op=op:t.command(op))
fails(lambda:t.command(0xfb01,(0x3000).to_bytes(4,'big')))
t.writes_enabled=True
for a in (0,0x1000,0x34000,0x7f000):fails(lambda a=a:t.command(0xfb01,a.to_bytes(4,'big')))
fails(lambda:t.command(0xfb04,struct.pack('>IH',0x3001,PAGE),out=b'\0'*PAGE))
fails(lambda:t.command(0xfb04,struct.pack('>IH',0x3000,512),out=b'\0'*512))
fails(lambda:t.command(0xfd05,struct.pack('>IH',SIZE,PAGE),n=PAGE))
fails(lambda:build(original,(ROOT/'unpacked/files/app.bin').read_bytes()+b'\0'*0x40000))
print('PASS: install, idempotence, exact restore, interrupted-write recovery, device mismatch, erase failure, backup-write failure, command/address bounds and oversize rejection.')
