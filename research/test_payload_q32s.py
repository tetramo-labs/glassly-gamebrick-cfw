"""Execute linked Q32S hooks in a bounded P-code model; stock services are stubs."""
from pathlib import Path
import json,unittest
from q32s_pcode import Machine
from device_profile import CUSTOM_OUT
R = Path(__file__).resolve().parent
META = json.loads((R.parent/'docs/evidence/q32s-payload.json').read_text())
SYM = {k:int(v,16) for k,v in META['symbols'].items()}

class PayloadMachine(Machine):
 def __init__(self):
  super().__init__()
  self.app=(CUSTOM_OUT/'app.bin').read_bytes()
  self.ccc=1;self.result=0;self.sent=[];self.handlers=0;self.stub_calls=[]
 def call(self,target,next_pc,gpio_high):
  self.reg('rets',next_pc)
  if target>=SYM['gb_task_entry']:
   return target
  args=[self.reg('r'+str(i)) for i in range(4)]
  self.stub_calls.append((target,args))
  if target==SYM['gb_stock_handler']:
   self.handlers+=1;value=0
  elif target==SYM['gb_stock_ccc']:
   assert args[:2]==[3,0x55],args;value=self.ccc
  elif target==SYM['gb_stock_att']:
   assert args[:2]==[3,0x54] and args[3]==4,args
   assert self.read('ram',self.reg('sp'),4)==0,'Fifth ATT argument'
   self.sent.append(bytes(self.read('ram',args[2]+i,1) for i in range(4)))
   value=self.result
  elif target==SYM['gb_stock_set_ccc']:
   assert args[:3]==[3,0x55,1],args
   self.ccc=args[2];value=17
  elif target==0x1e197d0:
   value=0
  elif target==SYM['gb_stock_ble_event']:
   assert args[:3]==[0x424c4500,7,9],args;value=23
  else:raise AssertionError(f'Unexpected external call {target:x}')
  self.reg('r0',value)
  for name in ('r1','r2','r3'):self.reg(name,0xa5a5a5a5)
  return next_pc

class PayloadTests(unittest.TestCase):
 def setUp(self):
  self.m=PayloadMachine();m=self.m
  m.reg('sp',0x9000)
  for i in range(4,16):m.reg('r'+str(i),0xabcd0000+i)
  for i in range(0x8e00,0x9004):m.write('ram',i,1,0xcd)
  m.execute(SYM['gb_task_entry'],0x1e0ee70)
  self.assertEqual(m.reg('sp'),0x8f80)
  self.assertEqual(m.reg('r8'),0x1e218ed)
  self.assertEqual(bytes(m.read('ram',0x8fd8+i,1) for i in range(40)),bytes(40))
  self.assertEqual(m.read('ram',0x9000,4),0xcdcdcdcd)
  self.assertEqual(bytes(m.read('ram',0x8f80+i,1) for i in range(88)),b'\xcd'*88)
  self.saved=[m.reg('r'+str(i)) for i in range(4,16)]
  m.write('ram',0x29e2,2,3)
 def tick(self,keys):
  m=self.m;m.write('ram',0x2a78,4,keys)
  before=m.handlers;m.execute(0x1e0f194,0x1e0f198)
  self.assertEqual(m.handlers,before+1)
  self.assertEqual(m.reg('sp'),0x8f80)
  self.assertEqual([m.reg('r'+str(i)) for i in range(4,16)],self.saved)
  self.assertEqual(bytes(m.read('ram',0x8f80+i,1) for i in range(88)),b'\xcd'*88)
 def test_initial_press_release_retry(self):
  m=self.m;self.tick(0);self.assertEqual(m.sent[-1],bytes([0x47,1,0,0]))
  m.result=-100;self.tick(0xf0003);self.tick(0)
  m.result=0;self.tick(0);self.assertEqual(m.sent[-1],bytes([0x47,1,1,63]))
  self.tick(0);self.assertEqual(m.sent[-1],bytes([0x47,1,2,0]))
  count=len(m.sent);self.tick(0);self.assertEqual(len(m.sent),count)
 def test_lifecycle_hooks(self):
  m=self.m;self.tick(0)
  for site,stop,args,ret in [(0x1e04b86,0x1e04b8a,[3,0x55,1],17),(0x1e05248,0x1e001d0,[7,9],23)]:
   m.reg('rets',stop)
   for i,arg in enumerate(args):m.reg('r'+str(i),arg)
   epoch=m.read('ram',0x40b8,4);m.execute(site,stop)
   self.assertEqual(m.read('ram',0x40b8,4),epoch+1)
   self.assertEqual(m.reg('r0'),ret);self.assertEqual(m.reg('sp'),0x8f80)
   self.assertEqual([m.reg('r'+str(i)) for i in range(4,16)],self.saved)
   count=len(m.sent);self.tick(0);self.assertEqual(len(m.sent),count+1)
 def test_boot_epoch_clear_stops_before_code(self):
  m=self.m
  for a in range(0x40b4,0x40c4):m.write('ram',a,1,0xcd)
  m.execute(0x1e00130,0x1e0014e,max_steps=10000)
  self.assertEqual(m.read('ram',0x40b8,4),0)
  self.assertEqual(m.read('ram',0x40bc,4),0xcdcdcdcd)
  self.assertEqual(m.read('ram',0x40c0,4),0xcdcdcdcd)
if __name__=='__main__':unittest.main()
