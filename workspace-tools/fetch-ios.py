#!/usr/bin/env python3
"""Fetch only the iPhone X 20H392 components needed by the local iOS root.

Downloads come from Apple's CDN, with ZIP CRC and BuildManifest SHA-384
verification. Apple binaries stay in ignored downloads/, never in Git.
"""
import hashlib
import json
from pathlib import Path
import plistlib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/tools'))
import remotezip

OUT = ROOT / 'downloads/ios-20H392'
URL = ('https://updates.cdn-apple.com/2025FallFCS/fullrestores/122-77006/'
       '1158E502-D76D-4226-AA06-ED5E30CD1111/'
       'iPhone10,3,iPhone10,6_16.7.16_20H392_Restore.ipsw')

def digest(path, algorithm):
    value = hashlib.new(algorithm)
    with path.open('rb') as source:
        while chunk := source.read(8 << 20):
            value.update(chunk)
    return value.hexdigest()

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    entries = remotezip.central_dir(URL)
    index = {entry[0]: entry for entry in entries}
    remotezip.extract(URL, index['BuildManifest.plist'], str(OUT))
    manifest = plistlib.loads((OUT / 'BuildManifest.plist').read_bytes())
    if (manifest['ProductVersion'], manifest['ProductBuildVersion']) != ('16.7.16', '20H392'):
        raise SystemExit('Unexpected firmware identity')
    identity = next(item for item in manifest['BuildIdentities']
                    if item['Info']['DeviceClass'] == 'd22ap'
                    and item['Info']['RestoreBehavior'] == 'Erase')
    records = []
    for component in ['DeviceTree', 'Cryptex1,AppOS', 'Cryptex1,SystemOS', 'OS']:
        info = identity['Manifest'][component]
        name = info['Info']['Path']
        remotezip.extract(URL, index[name], str(OUT))
        path = OUT / name
        actual = digest(path, 'sha384')
        expected = info['Digest'].hex()
        if actual != expected:
            raise SystemExit(f'{component}: BuildManifest SHA384 mismatch: {actual} != {expected}')
        records.append(dict(component=component, path=name, size=path.stat().st_size,
                            sha384=actual, sha256=digest(path, 'sha256')))
        (OUT / 'verified-components.json').write_text(json.dumps({
            'url': URL, 'version': '16.7.16', 'build': '20H392',
            'device': 'd22ap', 'components': records}, indent=2) + '\n')
        print(f'VERIFIED {component}: {path.stat().st_size} bytes; BuildManifest SHA384 matches', flush=True)

if __name__ == '__main__':
    main()
