"""Apply the pinned seven-sector patch while preserving declared runtime storage.

The canonical code/layout/identity bytes remain exact-match requirements. Only
VM, BTIF and USERIF are variable; they are read twice, saved, and never written.
"""
from custom_image import STOCK_SHA, CUSTOM_SHA as CANONICAL_TARGET_SHA, SECTORS, BASE
from flash_stock import SIZE, SECTOR, STORAGE, program_image
from stock_update import digest, require, entry
from jltech.cipher import jl_sfc_cipher

def validate_templates(stock, custom):
    require(len(stock) == len(custom) == SIZE, 'Incorrect template size')
    require(digest(stock) == STOCK_SHA and digest(custom) == CANONICAL_TARGET_SHA,
            'Unreviewed firmware template')
    require([a for a in range(0, SIZE, SECTOR) if stock[a:a+SECTOR] != custom[a:a+SECTOR]] == SECTORS,
            'Unexpected patch sectors')
    for template in (stock, custom):
        plain = bytearray(template)
        jl_sfc_cipher(plain, BASE, 0x100, BASE, 0x190d)
        for offset, (name, start, length, flags) in zip((96, 160, 192), STORAGE):
            record = entry(plain, BASE + offset)
            require(record[1] == 0xffff and record[2:6] == (start, length, flags, 0x81)
                    and record[-1].split(b'\0')[0].decode() == name,
                    'Reserved partition layout mismatch: ' + name)
            require(start % SECTOR == length % SECTOR == 0 and start + length <= 0x7f000,
                    'Storage overlaps key/MAC or unaligned sector')
            require(not any(start <= a < start + length for a in SECTORS), 'Storage overlaps patch')

def normalized(data, reference):
    output = bytearray(data)
    for _, start, length, _ in STORAGE:
        output[start:start+length] = reference[start:start+length]
    return bytes(output)

def plan(current, stock, custom, mode):
    validate_templates(stock, custom)
    require(mode in ('install', 'restore'), 'Invalid operation')
    require(len(current) == SIZE, 'Incomplete source snapshot')
    fixed = normalized(current, stock)
    if mode == 'install':
        require(fixed in (stock, custom),
                'Firmware, bootloader, partition map or identity mismatch; no writes allowed')
    else:
        # Recovery permits damaged bytes only in the seven reviewed write sectors.
        for a in range(0, SIZE, SECTOR):
            if a not in SECTORS:
                require(fixed[a:a+SECTOR] == stock[a:a+SECTOR],
                        f'Protected firmware/identity sector {a:#x} differs; refusing recovery')
    before_stock, after_custom = bytearray(stock), bytearray(custom)
    regions = []
    for name, start, length, _ in STORAGE:
        data = current[start:start+length]
        before_stock[start:start+length] = data
        after_custom[start:start+length] = data
        regions.append({'name': name, 'start': hex(start), 'size': length, 'sha256': digest(data),
                        'different_bytes_from_template': sum(a != b for a,b in zip(data,stock[start:start+length]))})
    before_stock, after_custom = bytes(before_stock), bytes(after_custom)
    desired = after_custom if mode == 'install' else before_stock
    for a in range(0, SIZE, SECTOR):
        if a not in SECTORS:
            require(desired[a:a+SECTOR] == current[a:a+SECTOR], 'Plan would alter protected bytes')
    report = {'mode': mode, 'before_sha256': digest(current), 'stock_sha256': digest(before_stock),
              'custom_sha256': digest(after_custom), 'desired_sha256': digest(desired),
              'canonical_stock_sha256': STOCK_SHA, 'canonical_custom_sha256': CANONICAL_TARGET_SHA,
              'storage_preserved': regions, 'changed_sectors': SECTORS,
              'source_state': 'stock' if fixed == stock else 'custom' if fixed == custom else 'partial patch'}
    return before_stock, after_custom, report

def program_preserving_storage(device, stock, custom, mode, save):
    require(not device.writes_enabled, 'Unexpected enabled writer')
    print('Reading all flash twice before allowing writes.', flush=True)
    first = device.read(0, SIZE)
    require(len(first) == SIZE, 'Incomplete first flash read')
    # Persist the first read even if identity validation or the second read fails.
    save('before.bin', first)
    second = device.read(0, SIZE)
    require(second == first, 'Flash changed between preflight reads; no writes allowed')
    source, target, report = plan(first, stock, custom, mode)
    save('restore-stock.bin', source)
    save('target.bin', target if mode == 'install' else source)
    import json
    save('preflight.json', (json.dumps(dict(report, matching_full_reads=2), indent=2)+'\n').encode())
    print('Firmware and identity verified; preserving VM, BTIF and USERIF.', flush=True)
    print('Target SHA256:', report['desired_sha256'], flush=True)
    try:
        result = program_image(device, source, target, mode, before=first)
    finally:
        device.writes_enabled = False
    return dict(report, **result, matching_full_reads=2)
