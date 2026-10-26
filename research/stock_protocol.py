"""Observed stock Gamebrick USB/BLE framing and GET-only MessagePack requests."""
import struct
GETTERS=('get_info','get_kb','get_mouse','get_cs','get_mt','get_xinput','get_dinput','get_sleep','get_screen')

def get_frame(command='get_info'):
    if command not in GETTERS: raise ValueError('GET-only command allowlist')
    payload=b'\x82\xa3cmd'+bytes([0xa0+len(command)])+command.encode()+b'\xa3key\xa3all'
    return bytes([0xb5,len(payload)+3,0xcc])+payload

class Frames:
    """Validate and join B4 response fragments. USB report padding is discarded."""
    def __init__(self):self.pending=None
    def feed(self,raw):
        if len(raw)<4 or raw[0]!=0xb4:raise ValueError('Not a B4 response')
        n,seq,command=raw[1:4];remaining=seq&127
        if not 4<=n<=min(64,len(raw)) or not 1<=remaining<=64:raise ValueError('Invalid frame bounds')
        if seq&128:self.pending=(command,remaining,bytearray())
        if self.pending is None:raise ValueError('Missing first fragment')
        cmd,expected,data=self.pending
        if command!=cmd or remaining!=expected:raise ValueError('Fragment sequence mismatch')
        data.extend(raw[4:n])
        if len(data)>4096:raise ValueError('Reply too long')
        if remaining==1:self.pending=None;return command,bytes(data)
        self.pending=(cmd,remaining-1,data)
        return None

def unpack(data):
    """Bounded MessagePack decoder for captured configuration responses."""
    pos=0
    def take(n):
        nonlocal pos
        if n<0 or pos+n>len(data):raise ValueError('Truncated MessagePack')
        out=data[pos:pos+n];pos+=n;return out
    def integer(n,signed=False):return int.from_bytes(take(n),'big',signed=signed)
    def value(depth=0):
        if depth>24:raise ValueError('Nested too deeply')
        tag=integer(1)
        if tag<128:return tag
        if tag>=224:return tag-256
        if 160<=tag<=191:return take(tag&31).decode('utf-8')
        if tag in (0xc0,0xc2,0xc3):return {0xc0:None,0xc2:False,0xc3:True}[tag]
        if 0xcc<=tag<=0xcf:return integer(1<<(tag-0xcc))
        if 0xd0<=tag<=0xd3:return integer(1<<(tag-0xd0),True)
        if tag in (0xca,0xcb):return struct.unpack('>f' if tag==0xca else '>d',take(4 if tag==0xca else 8))[0]
        if tag in (0xd9,0xda,0xdb):return take(integer(1<<(tag-0xd9))).decode('utf-8')
        if tag in (0xc4,0xc5,0xc6):return {'binary':take(integer(1<<(tag-0xc4))).hex()}
        if 0xd4<=tag<=0xd8 or tag in (0xc7,0xc8,0xc9):
            n=1<<(tag-0xd4) if tag>=0xd4 else integer(1<<(tag-0xc7))
            typ=integer(1,True);return {'extension':typ,'data':take(n).hex()}
        if 0x90<=tag<=0x9f or tag in (0xdc,0xdd):
            n=tag&15 if tag<0xa0 else integer(2 if tag==0xdc else 4)
            if n>4096:raise ValueError('Array too large')
            return [value(depth+1) for _ in range(n)]
        if 0x80<=tag<=0x8f or tag in (0xde,0xdf):
            n=tag&15 if tag<0x90 else integer(2 if tag==0xde else 4)
            if n>4096:raise ValueError('Map too large')
            out={}
            for _ in range(n):
                key=value(depth+1);out[key]=value(depth+1)
            return out
        raise ValueError(f'Unsupported MessagePack tag {tag:02x}')
    result=value()
    if pos!=len(data):raise ValueError(f'Trailing bytes: {len(data)-pos}')
    return result
