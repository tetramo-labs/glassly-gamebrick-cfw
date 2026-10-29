"""Compare the independent upstream unpacker's output with reviewed payloads."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
from device_profile import CUSTOM_OUT, NAME
base=CUSTOM_OUT/'independent-unpack'
pairs=[('files/app.bin',CUSTOM_OUT/'app.bin')]
pairs += [('files/'+name, ROOT/'unpacked/files'/name) for name in ['cfg_tool.bin','p11_code.bin']]
pairs += [('top/'+name, ROOT/'unpacked/top'/name) for name in ['uboot.boot','isd_config.ini']]
results={}
for name,expected in pairs:
    actual=(base/name).read_bytes()
    if actual != expected.read_bytes(): raise RuntimeError('Independent extraction differs: '+name)
    results[name]={'bytes':len(actual),'sha256':hashlib.sha256(actual).hexdigest()}
(ROOT.parent/f'docs/evidence/custom-extraction-{NAME}.json').write_text(json.dumps(results,indent=2)+'\n')
print('Independent extraction verified: app, config, P11, bootloader and chip configuration.')
