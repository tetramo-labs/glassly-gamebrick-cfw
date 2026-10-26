"""Verify preserved original flash and installed application without touching USB."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
metadata=json.loads((root/'docs/device-backup.json').read_text())
backup=root/'research/device-backup-20261022-233350'
for name in ('flash-pass1.bin','flash-pass2.bin'):
 data=(backup/name).read_bytes()
 assert len(data)==metadata['size'],name
 assert hashlib.sha256(data).hexdigest()==metadata['sha256'],name
app=(backup/'unpacked/files/app.bin').read_bytes()
assert len(app)==196224
assert hashlib.sha256(app).hexdigest()=='902aedc30a84c9ae777e3cbdd12ff5737ac17b7ee3f5288f76c7aa86fe267c97'
print('Verified both original flash copies and the installed application.')
