"""Generate conservative Ghidra seeds from exact stock Q32S firmware."""
from pathlib import Path
import hashlib
import pypcode
ROOT=Path(__file__).resolve().parent
b=(ROOT/'unpacked/files/app.bin').read_bytes()
assert hashlib.sha256(b).hexdigest()=='2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259'
a=pypcode.Arch('Jieli',str(ROOT/'q32s-analysis/processor/data/languages/JieLi.ldefs'))
c=pypcode.Context(next(x for x in a.languages if x.id=='q32s:LE:32:default'))
segments=[(0,0x1e00120,0x1d600),(0x2dea8,0x840,0xc60),(0x2eb08,0x40c0,0x1d88)]
seeds={0x1e0ee68:"emf_task",0x1e0ce10:"button_report_handler",0x1e13b5a:"att_copy_to_queue",0x1e1b08a:"cbuf_write",0x1e04b80:"set_ccc_and_sync",0x4c62:'transport_tx_ram',0x1e04c84:'att_write_callback',0x1e064ce:'command_frame_tx',0x1e0c122:'keyboard_report_sender',0x1e00120:'app_entry',0x1e034b4:'att_send',0x1e0420c:'ble_hid_data_send',0x1e04250:'ae42_send',0x1e041ba:'report_ccc_ready',0x1e06180:'vendor_transport_send',0x1e075e6:'vendor_command_dispatch',0x1e09f3e:'vendor_frame_receive',0x1e0614e:'cmp_read_map_inferred',0x1e06114:'cmp_read_array_inferred',0x1e060b8:'cmp_read_str_inferred',0x1e05d2a:'cmp_read_object_inferred'}
for fileoff,base,size in segments:
 for off in range(0,size,2):
  try:
   i=c.disassemble(b[fileoff+off:fileoff+off+16],base+off,max_instructions=1).instructions[0]
   if i.mnem not in ('call','goto') or not i.body.startswith('0x'):continue
   target=int(i.body,16)
   for fo,ba,sz in segments:
    if ba<=target<ba+sz:
     p=fo+target-ba
     first=c.disassemble(b[p:p+16],target,max_instructions=1).instructions[0]
     if first.mnem=='push':seeds.setdefault(target,'')
  except (pypcode.BadDataError,pypcode.UnimplError):pass
out=ROOT/'q32s-analysis/seeds.txt'
out.write_text(''.join(f'{addr:x} {name}\n' for addr,name in sorted(seeds.items())))
print(f'{len(seeds)} candidate entry points: {out}')
