"""Read-only OEM queries. Defaults to packet preview; --usb talks to one exact HID interface."""
import argparse,json,time

def short_frame(command,payload=b''):
    if command not in (1,3,4,5,0xcc): raise ValueError('Only reviewed GET commands permitted')
    if command==0xcc and payload!=INFO: raise ValueError('Only get_info/all permitted')
    frame=bytes((0xb5,3+len(payload),command))+payload
    if len(frame)>64: raise ValueError('Single USB packet only')
    return frame

# MessagePack fixmap with the cmd entry first, as required by the dispatcher.
INFO=b'\x82\xa3cmd\xa8get_info\xa3key\xa3all'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--usb',action='store_true');args=parser.parse_args()
    frames=[short_frame(c) for c in (1,3,4,5)]+[short_frame(0xcc,INFO)]
    if not args.usb:
        print(json.dumps([f.hex() for f in frames],indent=2));return
    import hid
    matches=[d for d in hid.enumerate(0x4353,0x8009) if d.get('usage_page')==0xff80 and d.get('usage')==1]
    if len(matches)!=1: raise SystemExit(f'Expected one Gamebrick vendor interface, found {len(matches)}')
    d=hid.device();d.open_path(matches[0]['path'])
    try:
        for frame in frames:
            n=d.write(b'\0'+frame+bytes(64-len(frame)))
            print(json.dumps({'direction':'tx','frame':frame.hex(),'written':n}),flush=True)
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                result=d.read(64,200)
                if result:print(json.dumps({'direction':'rx','frame':bytes(result).hex()}),flush=True)
    finally:d.close()

if __name__=='__main__':main()
