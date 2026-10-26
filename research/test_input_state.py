"""Compare recovered C against execution of stock GPIO-scan P-code."""
from pathlib import Path
import ctypes,random,unittest
from q32s_pcode import Machine
ROOT=Path(__file__).resolve().parent
class State(ctypes.Structure):_fields_=[(x,ctypes.c_uint32) for x in ('last_tick','candidate','stable','keys')]
class InputTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.lib=ctypes.CDLL(str(ROOT/'q32s-analysis/libinput_state.dylib'))
  cls.lib.gb_scan_step.argtypes=[ctypes.POINTER(State),ctypes.c_uint32,ctypes.c_uint32]
  cls.lib.gb_compact_keys.argtypes=[ctypes.c_uint32];cls.lib.gb_compact_keys.restype=ctypes.c_ubyte
 def test_stock_scan_equivalence(self):
  rng=random.Random(1161);m=Machine();s=State();m.reg('r14',0x29b0)
  tick=0xfffffe00
  for n in range(512):
   tick=(tick+rng.choice([0,1,99,100,101,500]))&0xffffffff
   high=rng.getrandbits(32) if n%3==0 else high
   m.write('ram',0x2adc,4,tick)
   m.execute(0x1e0ce34,0x1e0cee6,high)
   self.lib.gb_scan_step(ctypes.byref(s),tick,high)
   self.assertEqual([m.read('ram',a,4) for a in (0x2a7c,0x2a8c,0x2a90,0x2a78)],[s.last_tick,s.candidate,s.stable,s.keys])
 def test_wire_mapping_all_combinations(self):
  for wire in range(64):
   stock=((wire&15)<<16)|((wire>>4)&3)|0x80401000
   self.assertEqual(self.lib.gb_compact_keys(stock),wire)
 def test_press_bounce_release(self):
  s=State();all_high=0xffffffff
  for tick,high,expected in [(100,all_high^1,0),(200,all_high,0),(300,all_high^1,0),(400,all_high^1,1<<17),(500,all_high,1<<17),(600,all_high,0)]:
   self.lib.gb_scan_step(ctypes.byref(s),tick,high);self.assertEqual(s.keys,expected)
if __name__=='__main__':unittest.main()
