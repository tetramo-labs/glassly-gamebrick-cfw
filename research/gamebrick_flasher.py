"""One-shot Gamebrick flasher: take any known Gamebrick Mini straight to the Glassly firmware.

Everything is derived from the connected unit's own flash. The flash is read twice and kept
as a backup; its storage-independent fingerprint must match the factory image, the official
update or the Glassly image. The Glassly and official applications ship in firmware/dist and
are hash-pinned; the official update archive is only needed to rebuild them. VM/BTIF/USERIF
and the key/MAC sector are never written.
"""
import hashlib, io, json, subprocess, sys, tempfile, urllib.request, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'jl-misctools/firmware'))
from stock_update import build, digest, require, OEM_SHA
from custom_image import patch_app

STORAGE_START, SIZE = 0x7a000, 0x80000  # VM, BTIF, USERIF, then the (blank) key/MAC sector

# SHA256 of a flash image with its runtime storage and key/MAC sector zeroed: the same for every
# unit seen so far (unit1 and unit2), because only those regions differ between controllers.
FINGERPRINTS = {
    '62153ccb490b114cc604501526a72c505c27796b1778b07761fab156985a45d9': 'factory',
    'dc16ee8a3dba5468cc7ad3b0af4e7a714d018a4b9eda929d877d233ec9b4958c': 'stock',
    'c482ad55d3fab1086d889673fd8dd9a832ba1ccc6188bad71bf4f90597a0c5bc': 'custom',
    'acc50d0b7b83e3e02480ff3ec87c8c0ee474489f59f4eb33bd22eeb6f5cd2099': 'withdrawn',  # 2026-10-25 image; reset loop
}

OEM_ZIP_URL = 'https://media.iine.top/legacy-assets/6dd5d46599c6e1eeb8bd2623c15d14c7a3aee61163f46da0df38953c690dac61-zip'
OEM_ZIP_SHA = '6dd5d46599c6e1eeb8bd2623c15d14c7a3aee61163f46da0df38953c690dac61'
OEM_UFW_SHA = '73005e7c885aab2a644adfdf2dbadc01802b34427e9e6febf823f50d4d7745e9'
CUSTOM_APP_SHA = '495ce9131d2cadebd558ec6d5ebfd51b6afa1ba957cba5c7f5dd331fcba9f432'
DIST = ROOT.parent/'firmware/dist'
PAYLOAD = DIST/'vendor-payload.bin'
GLASSLY_APP = DIST/'glassly-gamebrick-app.bin'
OFFICIAL_APP = DIST/'iine-official-app.bin'
MANIFEST = ROOT.parent/'docs/evidence/q32s-payload.json'


def fingerprint(image):
    require(len(image) == SIZE, 'Incorrect image size')
    masked = bytearray(image)
    masked[STORAGE_START:SIZE] = bytes(SIZE - STORAGE_START)
    return hashlib.sha256(masked).hexdigest()


def classify(image):
    return FINGERPRINTS.get(fingerprint(image), 'unknown')


def oem_archive(path=None, log=print):
    """The official update ZIP: a local copy, a cached download, or a fresh one. Hash-pinned."""
    cache = ROOT/'stock-update.zip'
    for candidate in ([Path(path)] if path else []) + [cache]:
        if candidate.exists():
            data = candidate.read_bytes()
            require(digest(data) == OEM_ZIP_SHA, f'{candidate} is not the pinned IINE update archive')
            return data
    log(f'Downloading the official IINE update ({OEM_ZIP_URL})')
    with urllib.request.urlopen(OEM_ZIP_URL, timeout=120) as response:
        data = response.read()
    require(digest(data) == OEM_ZIP_SHA, 'Downloaded archive hash differs from the pinned IINE update')
    cache.write_bytes(data)
    return data


def oem_application(archive=None):
    """The unmodified official application: the committed copy, or extracted from the update
    archive with the independent upstream unpacker. Hash-pinned either way."""
    if archive is None:
        app = OFFICIAL_APP.read_bytes()
        require(digest(app) == OEM_SHA, 'Committed official application hash mismatch')
        return app
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        members = [m for m in z.namelist() if m.lower().endswith('.ufw')]
        require(len(members) == 1, 'Expected one .ufw in the update archive')
        ufw = z.read(members[0])
    require(digest(ufw) == OEM_UFW_SHA, 'Update firmware hash differs from the pinned IINE reader update')
    tool = ROOT/'jl-misctools/firmware'
    with tempfile.TemporaryDirectory() as temp:
        (Path(temp)/'stock.ufw').write_bytes(ufw)
        result = subprocess.run([sys.executable, '-E', '-s', str(tool/'fwunpack_newfw.py'), '--dirname', temp + '/out', temp + '/stock.ufw'],
                                capture_output=True, text=True, cwd=tool)
        require(result.returncode == 0, 'Unpacking the official update failed: ' + result.stderr[-400:])
        app = (Path(temp)/'out/files/app.bin').read_bytes()
    require(digest(app) == OEM_SHA, 'Official application hash mismatch')
    return app


def custom_application(oem=None):
    """The reviewed Glassly application: the committed copy, or the OEM bytes plus the pinned
    hooks and payload. Hash-pinned either way."""
    if oem is None:
        app = GLASSLY_APP.read_bytes()
        require(digest(app) == CUSTOM_APP_SHA, 'Committed Glassly application hash mismatch')
        return app
    payload = PAYLOAD.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    require(digest(payload) == manifest['payload_sha256'], 'Payload differs from the reviewed build')
    patched, _ = patch_app(oem, payload, manifest, decode=False)
    require(digest(patched) == CUSTOM_APP_SHA, 'Patched application differs from the reviewed hash')
    return patched


def plan(current, oem, mode, custom=None):
    """Source and target images for `mode` from the live flash, both carrying its storage.
    `custom` defaults to the committed Glassly application."""
    state = classify(current)
    require(state in ('factory', 'stock', 'custom'), f'Unrecognised flash contents ({state}); refusing to write. Keep the saved backup and ask for help.')
    sha = digest(current)
    stock = build(current, oem, sha)
    if mode == 'install':
        target = build(current, custom or custom_application(), sha)
    elif mode == 'restore':
        target = stock
    else:
        raise RuntimeError('Invalid operation')
    require(fingerprint(target) in FINGERPRINTS and FINGERPRINTS[fingerprint(target)] == ('custom' if mode == 'install' else 'stock'),
            'Derived image does not match the reviewed fingerprint')
    require(target[STORAGE_START:] == current[STORAGE_START:], 'Plan would alter runtime storage or key/MAC')
    sectors = [a for a in range(0, SIZE, 4096) if current[a:a+4096] != target[a:a+4096]]
    return {'state': state, 'target': target, 'stock': stock, 'changed_sectors': sectors,
            'current_sha256': sha, 'target_sha256': digest(target), 'stock_sha256': digest(stock)}
