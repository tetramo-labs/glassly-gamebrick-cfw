"""Regression checks against real controller replies and BD19 ROM addresses."""
from pathlib import Path
import json,unittest,pypcode
from stock_protocol import Frames,GETTERS,get_frame,unpack
ROOT=Path(__file__).resolve().parent
class ProtocolTests(unittest.TestCase):
 def test_live_reply_replay(self):
  decoder=Frames();actual={};expected={}
  for line in (ROOT.parent/'docs/evidence/stock-usb-settings.jsonl').read_text().splitlines():
   row=json.loads(line)
   if row.get('direction')=='rx':
    reply=decoder.feed(bytes.fromhex(row['frame']))
    if reply:actual[row['query']]=unpack(reply[1])
   elif 'decoded' in row:expected[row['query']]=row['decoded']
  self.assertEqual(actual,expected);self.assertEqual(set(actual),set(GETTERS))
  self.assertEqual(actual['get_info']['version'],0x300)
  self.assertEqual([v['key'] for v in actual['get_mouse']['map']],[0,1,16,17,18,19])
 def test_get_allowlist(self):
  for name in GETTERS:
   frame=get_frame(name);self.assertEqual(frame[:3],bytes([0xb5,len(frame),0xcc]))
   self.assertEqual(unpack(frame[3:]),{'cmd':name,'key':'all'})
  with self.assertRaises(ValueError):get_frame('set_restore')
 def test_fragment_rejection(self):
  for raw in [b'',bytes.fromhex('b4038101'),bytes.fromhex('b4058101'),bytes.fromhex('b4040001'),bytes.fromhex('b4040101')]:
   with self.assertRaises(ValueError):Frames().feed(raw)
  d=Frames();d.feed(bytes.fromhex('b4058201aa'))
  with self.assertRaises(ValueError):d.feed(bytes.fromhex('b4050102bb'))
 def test_msgpack_rejection(self):
  for data in [b'',b'\xcc',b'\x81',b'\xa5x',b'\xc1',b'\x00\x00',b'\xdd\xff\xff\xff\xff']:
   with self.assertRaises(ValueError):unpack(data)
 def test_rom_and_ram_call_targets(self):
  b=(ROOT/'unpacked/files/app.bin').read_bytes()
  a=pypcode.Arch('Jieli',str(ROOT/'q32s-analysis/processor/data/languages/JieLi.ldefs'))
  c=pypcode.Context(next(x for x in a.languages if x.id=='q32s:LE:32:default'))
  for offset,address,expected in [(0x7698,0x1e077b8,0x106ef4),(0x4b4a,0x1e04c6a,0x106ee4),(0x2f758,0x4d10,0x1e0420c),(0x2f80a,0x4dc2,0x1e06180)]:
   i=c.disassemble(b[offset:offset+16],address,max_instructions=1).instructions[0]
   self.assertEqual(i.mnem,'call');self.assertEqual(int(i.body,16),expected)
if __name__=='__main__':unittest.main()
