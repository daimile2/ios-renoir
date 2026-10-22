#!/usr/bin/env python3
"""Read and validate primary/backup GPT metadata for all six renoir UFS LUNs."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]

def adb(command, root_prefix):
    return subprocess.check_output(['adb', 'exec-out', *(root_prefix), command], timeout=60)

def check_header(data, sector_size, header_offset, window_first_lba):
    header = data[header_offset:header_offset + sector_size]
    if header[:8] != b'EFI PART':
        raise ValueError('GPT signature missing')
    size, expected = struct.unpack_from('<II', header, 12)
    if not 92 <= size <= sector_size:
        raise ValueError('Invalid GPT header size')
    copy = bytearray(header[:size])
    copy[16:20] = bytes(4)
    if zlib.crc32(copy) != expected:
        raise ValueError('GPT header CRC mismatch')
    current, alternate = struct.unpack_from('<QQ', header, 24)
    table_lba, count, entry_size, table_crc = struct.unpack_from('<QIII', header, 72)
    start = (table_lba - window_first_lba) * sector_size
    length = count * entry_size
    if start < 0 or start + length > len(data):
        raise ValueError('GPT table does not fit captured window')
    table = data[start:start + length]
    if zlib.crc32(table) != table_crc:
        raise ValueError('GPT partition array CRC mismatch')
    partitions = []
    for index in range(count):
        entry = table[index*entry_size:(index+1)*entry_size]
        if entry[:16] == bytes(16):
            continue
        first, last = struct.unpack_from('<QQ', entry, 32)
        name = entry[56:128].decode('utf-16le').split('\0')[0]
        partitions.append(dict(name=name, first_lba=first, last_lba=last))
    return dict(current_lba=current, alternate_lba=alternate, table_lba=table_lba,
                table_crc32=f'{table_crc:08x}', partitions=partitions)

def main():
    identity = adb('id', [])
    prefix = [] if b'uid=0(' in identity else ['su', '-c']
    if adb('getprop ro.product.device', prefix).strip() != b'renoir':
        raise SystemExit('Expected renoir')
    destination = ROOT / 'backup/gpt'
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for lun in ['sda', 'sdb', 'sdc', 'sdd', 'sde', 'sdf']:
        device = '/dev/block/' + lun
        sector_size = int(adb('blockdev --getss ' + device, prefix))
        size = int(adb('blockdev --getsize64 ' + device, prefix))
        sectors = size // sector_size
        if sector_size not in (512, 4096) or sectors < 67 or size % sector_size:
            raise SystemExit('Unexpected LUN geometry: ' + lun)
        primary = adb(f'dd if={device} bs={sector_size} count=34 2>/dev/null', prefix)
        backup = adb(f'dd if={device} bs={sector_size} skip={sectors-33} count=33 2>/dev/null', prefix)
        if len(primary) != 34*sector_size or len(backup) != 33*sector_size:
            raise SystemExit('Short GPT read: ' + lun)
        first = check_header(primary, sector_size, sector_size, 0)
        last = check_header(backup, sector_size, 32*sector_size, sectors-33)
        if (first['current_lba'], first['alternate_lba'], last['current_lba'], last['alternate_lba']) != (1, sectors-1, sectors-1, 1):
            raise SystemExit('GPT header locations disagree: ' + lun)
        if first['partitions'] != last['partitions'] or first['table_crc32'] != last['table_crc32']:
            raise SystemExit('Primary and backup GPT disagree: ' + lun)
        hashes = {}
        for kind, data in [('primary', primary), ('backup', backup)]:
            path = destination / f'{lun}-{kind}.bin'
            if path.exists() and path.read_bytes() != data:
                raise SystemExit('Preserving different existing GPT backup: ' + str(path))
            path.write_bytes(data)
            hashes[path.name] = hashlib.sha256(data).hexdigest()
        records.append(dict(lun=lun, sector_size=sector_size, bytes=size,
                            hashes=hashes, primary=first, backup=last))
        (destination / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
        print(f'VERIFIED {lun}: both GPT header CRCs and partition array CRCs; {len(first["partitions"])} partitions', flush=True)

if __name__ == '__main__':
    main()
