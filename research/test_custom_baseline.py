"""Exercise exact-readback rebase plus the existing installer/recovery test suite."""
import contextlib, io, unittest
import test_custom_image
from custom_baseline import prepare_current, rebase, BASELINE_SHA, CURRENT_TARGET_SHA
from custom_image import prepare
from stock_update import digest

class CurrentImageTests(test_custom_image.ImageTests):
 target_sha = CURRENT_TARGET_SHA
 @classmethod
 def setUpClass(cls):
  with contextlib.redirect_stdout(io.StringIO()):cls.stock,cls.target,cls.report=prepare_current()
 def test_reviewed_storage_is_preserved(self):
  self.assertEqual(digest(self.stock),BASELINE_SHA)
  self.assertEqual(self.target[0x7a000:0x7b000],self.stock[0x7a000:0x7b000])
  with contextlib.redirect_stdout(io.StringIO()):stock,canonical,_=prepare()
  differences=[i for i,(a,b) in enumerate(zip(canonical,self.target)) if a!=b]
  self.assertEqual(len(differences),38)
  self.assertTrue(all(0x7a3bf<=i<=0x7a3e7 for i in differences))
 def test_unreviewed_capture_rejected(self):
  with contextlib.redirect_stdout(io.StringIO()):stock,canonical,_=prepare()
  for address in [0,0x2140,0x7a3bf,0x7a900,0x7f100]:
   changed=bytearray(self.stock);changed[address]^=1
   with self.assertRaises(RuntimeError):rebase(stock,canonical,changed)

if __name__=='__main__':unittest.main()
