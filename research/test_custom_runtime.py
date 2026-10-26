"""Runtime-storage preservation, firmware rejection and NOR fault injection."""
import contextlib, io, random, unittest
from pathlib import Path
from custom_image import prepare, ROOT
from custom_runtime import plan, program_preserving_storage, STORAGE, SECTORS
from test_custom_image import NOR
from flash_stock import SIZE

class RuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with contextlib.redirect_stdout(io.StringIO()):cls.stock,cls.custom,_=prepare()
 def program(self,device,mode='install',save=None):
  if save is None:save=lambda name,data:None
  with contextlib.redirect_stdout(io.StringIO()):
   return program_preserving_storage(device,self.stock,self.custom,mode,save)
 def test_both_actual_captures(self):
  for directory in ['custom-flash-20261024-102322','custom-flash-20261025-132431']:
   before=(ROOT/directory/'before.bin').read_bytes();files={};d=NOR(before,SECTORS)
   report=self.program(d,save=files.__setitem__)
   self.assertEqual(report['writes'],7);self.assertEqual(files['before.bin'],before)
   self.assertEqual(files['target.bin'],bytes(d.data));self.assertEqual(files['restore-stock.bin'],before)
   self.assertEqual(self.program(d)['writes'],0)
   self.program(d,'restore');self.assertEqual(bytes(d.data),before)
 def test_storage_survives_all_interrupted_pages(self):
  before=bytearray(self.stock);rng=random.Random(1162)
  for _,a,n,_ in STORAGE:before[a:a+n]=rng.randbytes(n)
  baseline=NOR(before,SECTORS);self.program(baseline)
  self.assertEqual(baseline.pages,112)
  for page in range(1,113):
   with self.subTest(page=page):
    d=NOR(before,SECTORS,fail=page)
    with self.assertRaises(RuntimeError):self.program(d)
    for _,a,n,_ in STORAGE:self.assertEqual(d.data[a:a+n],before[a:a+n])
    d.fail=None;self.program(d,'restore');self.assertEqual(d.data,before)
 def test_unrelated_changes_are_rejected(self):
  for a in [0,0x1fff,0x2080,0x2140,0x6000,0x34000,0x40000,0x79fff,0x7f000,0x7ffff]:
   data=bytearray(self.stock);data[a]^=1;d=NOR(data,SECTORS)
   with self.subTest(address=hex(a)),self.assertRaises(RuntimeError):self.program(d)
   self.assertFalse(d.erased)
   if a//4096*4096 not in SECTORS:
    with self.assertRaises(RuntimeError):self.program(d,'restore')
 def test_unstable_reads_rejected(self):
  class Changing(NOR):
   reads=0
   def read(self,a,n):
    self.reads+=1
    if self.reads==2:self.data[0x7d001]^=1
    return super().read(a,n)
  d=Changing(self.stock,SECTORS);saved={}
  with self.assertRaises(RuntimeError):self.program(d,save=saved.__setitem__)
  self.assertFalse(d.erased);self.assertEqual(saved['before.bin'],self.stock)
 def test_each_artifact_must_save_before_erase(self):
  for fail_name in ['before.bin','restore-stock.bin','target.bin','preflight.json']:
   d=NOR(self.stock,SECTORS)
   def save(name,data):
    if name==fail_name:raise OSError('Disk full')
   with self.assertRaises(OSError):self.program(d,save=save)
   self.assertFalse(d.erased)
 def test_template_or_partition_tampering_rejected(self):
  for a in [0x2080,0x2140,0x7d001]:
   bad=bytearray(self.custom);bad[a]^=1
   with self.assertRaises(RuntimeError):plan(self.stock,self.stock,bad,'install')
 def test_restore_preserves_new_runtime_data(self):
  d=NOR(self.stock,SECTORS);self.program(d)
  d.data[0x7d001]^=1;current=bytes(d.data)
  self.program(d,'restore')
  self.assertEqual(d.data[:0x7a000],self.stock[:0x7a000])
  self.assertEqual(d.data[0x7a000:],current[0x7a000:])
if __name__=='__main__':unittest.main()
