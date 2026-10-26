"""Read the known stock configuration getters; never sends SET, reset or test-mode commands."""
import json,time
import hid
from stock_protocol import GETTERS,get_frame,Frames,unpack
matches=[d for d in hid.enumerate(0x4353,0x8009) if d.get('usage_page')==0xff80 and d.get('usage')==1]
if len(matches)!=1:raise SystemExit(f'Expected one Gamebrick vendor HID, found {len(matches)}')
d=hid.device();d.open_path(matches[0]['path'])
try:
 for name in GETTERS:
    frame=get_frame(name);d.write(b'\0'+frame+bytes(64-len(frame)))
    print(json.dumps({'query':name,'direction':'tx','frame':frame.hex()}),flush=True)
    deadline=time.monotonic()+3;decoder=Frames()
    while time.monotonic()<deadline:
        raw=bytes(d.read(64,200))
        if not raw:continue
        print(json.dumps({'query':name,'direction':'rx','frame':raw.hex()}),flush=True)
        try:
            reply=decoder.feed(raw)
            if reply:
                cmd,data=reply
                print(json.dumps({'query':name,'command':cmd,'decoded':unpack(data)}),flush=True)
                break
        except ValueError as e:print(json.dumps({'query':name,'decode_error':str(e)}),flush=True)
finally:d.close()
