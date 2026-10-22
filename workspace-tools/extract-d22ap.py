#!/usr/bin/env python3
"""Decode the manifest-verified D22AP IM4P locally, using upstream LZFSE."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/tools'))
import adt

def read_der(data, offset):
    tag = data[offset]
    size = data[offset + 1]
    offset += 2
    if size & 0x80:
        count = size & 0x7f
        if not count or count > 8:
            raise ValueError('Unsupported DER length')
        size = int.from_bytes(data[offset:offset + count], 'big')
        offset += count
    end = offset + size
    if end > len(data):
        raise ValueError('Truncated DER value')
    return tag, data[offset:end], end

def main():
    directory = ROOT / 'downloads/ios-20H392'
    source = directory / 'Firmware/all_flash/DeviceTree.d22ap.im4p'
    data = source.read_bytes()
    verified = json.loads((directory / 'verified-components.json').read_text())
    record = next(item for item in verified['components'] if item['component'] == 'DeviceTree')
    if hashlib.sha384(data).hexdigest() != record['sha384']:
        raise SystemExit('DeviceTree differs from verified BuildManifest component')
    tag, sequence, end = read_der(data, 0)
    if tag != 0x30 or end != len(data):
        raise SystemExit('Expected exactly one DER sequence')
    values = []
    cursor = 0
    while cursor < len(sequence):
        tag, value, cursor = read_der(sequence, cursor)
        values.append((tag, value))
    if values[0] != (0x16, b'IM4P') or values[1] != (0x16, b'dtre') or values[3][0] != 0x04:
        raise SystemExit('Expected an IM4P device-tree payload')
    packed = directory / 'd22ap.adt.lzfse'
    packed.write_bytes(values[3][1])
    destination = ROOT / 'src/research/ipsw-x/d22ap.adt'
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(ROOT / 'toolchain/lzfse/build/lzfse'), '-decode',
                    '-i', str(packed), '-o', str(destination)], check=True)
    blob = destination.read_bytes()
    tree, consumed = adt.parse(blob)
    products = [child for child in tree.children if child.name == 'product']
    if len(products) != 1 or consumed > len(blob):
        raise SystemExit('Decoded ADT is missing its unique /product node')
    print(json.dumps(dict(decoded_bytes=len(blob), parsed_bytes=consumed,
                          product_properties=len(products[0].props),
                          sha256=hashlib.sha256(blob).hexdigest())))

if __name__ == '__main__':
    main()
