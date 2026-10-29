"""Offline custom-image guard and NOR failure/recovery tests. No USB access."""
import contextlib,io,json,unittest
from custom_image import prepare,patch_app,ROOT,DEST
from flash_custom import TARGET_SHA
from flash_stock import program_image,SECTOR,PAGE,SIZE
from stock_update import digest

class NOR:
 def __init__(self,data,sectors,fail=None):
  self.data=bytearray(data);self.sectors=set(sectors);self.writes_enabled=False;self.erased=[];self.pages=0;self.fail=fail
 def read(self,a,n):return bytes(self.data[a:a+n])
 def erase(self,a):
  assert self.writes_enabled and a in self.sectors and a%SECTOR==0
  self.erased.append(a);self.data[a:a+SECTOR]=b'\xff'*SECTOR
 def program(self,a,b):
  assert self.writes_enabled and a//SECTOR*SECTOR in self.sectors and len(b)==PAGE and a%PAGE==0
  self.pages+=1
  if self.pages==self.fail:raise RuntimeError('Injected disconnect')
  assert all(x&y==y for x,y in zip(self.data[a:a+PAGE],b))
  self.data[a:a+PAGE]=b

class ImageTests(unittest.TestCase):
 target_sha = TARGET_SHA
 erased_sectors = 8
 @classmethod
 def setUpClass(cls):
  with contextlib.redirect_stdout(io.StringIO()): cls.stock,cls.target,cls.report=prepare()
 def program(self,device,mode):
  with contextlib.redirect_stdout(io.StringIO()):return program_image(device,self.stock,self.target,mode)
 def test_install_restore_and_idempotence(self):
  self.assertEqual(digest(self.target),self.target_sha)
  d=NOR(self.stock,self.report['changed_sectors']);r=self.program(d,'install')
  self.assertTrue(r['full_readback_verified']);self.assertEqual(bytes(d.data),self.target)
  self.assertEqual(d.erased[-1],0x2000);self.assertEqual(len(d.erased),self.erased_sectors)
  self.assertEqual(self.program(d,'install')['writes'],0)
  self.program(d,'restore');self.assertEqual(bytes(d.data),self.stock)
 def test_every_page_failure_restores_stock(self):
  baseline=NOR(self.stock,self.report['changed_sectors']);self.program(baseline,'install')
  for page in range(1,baseline.pages+1):
   with self.subTest(page=page):
    d=NOR(self.stock,self.report['changed_sectors'],page)
    with self.assertRaises(RuntimeError):self.program(d,'install')
    for a in range(0,SIZE,SECTOR):
     if a not in d.sectors:self.assertEqual(bytes(d.data[a:a+SECTOR]),self.stock[a:a+SECTOR])
    d.fail=None;self.program(d,'restore');self.assertEqual(bytes(d.data),self.stock)
 def test_unknown_flash_rejected(self):
  for address in [0,0x2140,0x6000,0x40000,0x7a3bf,0x7f100]:
   data=bytearray(self.stock);data[address]^=1
   d=NOR(data,self.report['changed_sectors'])
   with self.assertRaises(RuntimeError):self.program(d,'install')
   self.assertFalse(d.erased)
 def test_wrong_source_or_payload_rejected(self):
  app=(ROOT/'unpacked/files/app.bin').read_bytes();payload=(ROOT/'q32s-analysis/vendor-payload.bin').read_bytes()
  manifest=json.loads((ROOT.parent/'docs/evidence/q32s-payload.json').read_text())
  for a,p in [(b'\0'+app[1:],payload),(app,b'\0'+payload[1:])]:
   with self.assertRaises(RuntimeError):patch_app(a,p,manifest)
 def test_failed_backup_write_prevents_erase(self):
  d=NOR(self.stock,self.report['changed_sectors'])
  def fail(_):raise RuntimeError('Disk full')
  with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(RuntimeError):
   program_image(d,self.stock,self.target,'install',save_before=fail)
  self.assertFalse(d.erased)
if __name__=='__main__':unittest.main()
