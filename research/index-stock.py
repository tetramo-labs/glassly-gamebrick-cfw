"""Extract the stock GATT table, transport symbols and verified query evidence."""
from pathlib import Path
import hashlib,json,struct
ROOT=Path(__file__).resolve().parent;BASE=0x1e00120
b=(ROOT/'unpacked/files/app.bin').read_bytes()
sha=hashlib.sha256(b).hexdigest()
if sha!='2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259':raise SystemExit('Unexpected firmware')
# Full profile, distinguished from the separate single-service table at 0x1e21fb4.
p=0x21f9e;rows=[]
while struct.unpack_from('<H',b,p)[0]:
 n,flags,handle,uuid=struct.unpack_from('<4H',b,p)
 if not 8<=n<=256 or p+n>len(b):raise ValueError('Invalid ATT record')
 rows.append({'address':hex(BASE+p),'handle':hex(handle),'uuid':hex(uuid),'flags':hex(flags),'value':b[p+8:p+n].hex()});p+=n
assert len(rows)==91
assert {r['handle']:r['uuid'] for r in rows}['0x54']=='0xae42'
symbols={
 'app_entry':0x1e00120,'transport_tx_ram':0x4c62,'hid_call_in_ram':0x4d10,
 'vendor_call_in_ram':0x4dc2,'att_send':0x1e034b4,'report_ccc_ready':0x1e041ba,
 'ble_hid_data_send':0x1e0420c,'ae42_send':0x1e04250,'att_write_callback':0x1e04c84,
 'vendor_transport_send':0x1e06180,'command_frame_tx':0x1e064ce,
 'vendor_command_dispatch':0x1e075e6,'vendor_frame_receive':0x1e09f3e,
 'keyboard_report_sender':0x1e0c122,'report_processing_candidate':0x1e0ce10,
 'connection_handle_ram':0x29e2,'gatt_profile':0x1e220be,'hid_handle_table':0x1e22470}
evidence={'application_sha256':sha,'base':hex(BASE),'size':len(b),'symbols':{k:hex(v) for k,v in symbols.items()},'ram_copies':[{'file_offset':'0x2dea8','address':'0x840','length':'0xc60'},{'file_offset':'0x2eb08','address':'0x40c0','length':'0x1d88'}],'gatt':rows,'hid_report_handles':dict(zip(range(1,7),map(hex,struct.unpack_from('<6H',b,0x22352))))}
# Exact table is address BASE+0x22350; index zero is unused.
assert evidence['hid_report_handles']=={1:'0x27',2:'0x2b',3:'0x32',4:'0x36',5:'0x3a',6:'0x3e'}
settings=[json.loads(line) for line in (ROOT/'q32s-analysis/usb-settings.jsonl').read_text().splitlines()]
evidence['queries']=[r for r in settings if 'decoded' in r]
assert len(evidence['queries'])==9
out=ROOT.parent/'docs/evidence/q32s-stock-analysis.json';out.write_text(json.dumps(evidence,indent=2)+'\n')
print(out)
