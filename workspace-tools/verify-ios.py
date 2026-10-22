#!/usr/bin/env python3
"""Verify local Apple components against the downloaded D22AP BuildManifest."""
import argparse
import hashlib
from pathlib import Path
import plistlib
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paths', action='store_true', help='print OS, SystemOS, AppOS paths only')
    args = parser.parse_args()
    directory = ROOT / 'downloads/ios-20H392'
    manifest = plistlib.loads((directory / 'BuildManifest.plist').read_bytes())
    if (manifest['ProductVersion'], manifest['ProductBuildVersion']) != ('16.7.16', '20H392'):
        raise SystemExit('Unexpected firmware version')
    identity = next(item for item in manifest['BuildIdentities']
                    if item['Info']['DeviceClass'] == 'd22ap'
                    and item['Info']['RestoreBehavior'] == 'Erase')
    paths = []
    for component in ['OS', 'Cryptex1,SystemOS', 'Cryptex1,AppOS', 'DeviceTree']:
        record = identity['Manifest'][component]
        path = (directory / record['Info']['Path']).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise SystemExit('Component path escapes download directory')
        digest = hashlib.sha384()
        with path.open('rb') as source:
            while chunk := source.read(8 << 20):
                digest.update(chunk)
        if digest.digest() != record['Digest']:
            raise SystemExit(f'BuildManifest SHA384 mismatch: {component}')
        print(f'VERIFIED {component}: {path.stat().st_size} bytes', file=sys.stderr)
        paths.append(path)
    if args.paths:
        print('\n'.join(str(path) for path in paths[:3]))

if __name__ == '__main__':
    main()
