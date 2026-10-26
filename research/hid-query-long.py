import hid,time,json
matches=[d for d in hid.enumerate(0x4353,0x8009) if d.get('usage_page')==0xff80 and d.get('usage')==1]
print('Matching vendor interfaces:',len(matches),flush=True)
if len(matches)!=1: raise SystemExit('Expected exactly one Gamebrick vendor interface')
d=hid.device();d.open_path(matches[0]['path'])
try:
 for cmd in [1,3,4,5]:
  packet=bytes([0xa4,5,0x81,cmd,(0xa4+5+0x81+cmd)&255])
  n=d.write(b'\0'+packet+bytes(64-len(packet)))
  print('GET',hex(cmd),'wrote',n,flush=True)
  until=time.monotonic()+1
  while time.monotonic()<until:
   result=d.read(64,200)
   if result: print('RX',bytes(result).hex(' '),flush=True)
finally:d.close()
