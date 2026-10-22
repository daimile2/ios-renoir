#!/usr/bin/env python3
"""Read renoir calibration and boot partitions; verify sizes and device hashes."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'backup' / 'partitions'
PARTS = ['persist', 'persistbak', 'modemst1', 'modemst2', 'fsg', 'fsc',
         'devinfo', 'dtbo_a', 'dtbo_b', 'vbmeta_a', 'vbmeta_b',
         'vbmeta_system_a', 'vbmeta_system_b', 'boot_a', 'boot_b',
         'vendor_boot_a', 'vendor_boot_b']

def shell(command):
    return subprocess.check_output(['adb', 'shell', 'su', '-c', command], text=True).strip()

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if shell('getprop ro.product.device') != 'renoir':
        raise SystemExit('Refusing backup: expected renoir')
    records = []
    for name in PARTS:
        device = '/dev/block/by-name/' + name
        size = int(shell('blockdev --getsize64 ' + device))
        target = OUT / (name + '.img')
        remote = shell('sha256sum ' + device).split()[0]
        if not target.exists() or target.stat().st_size != size or hashlib.sha256(target.read_bytes()).hexdigest() != remote:
            temp = target.with_suffix('.partial')
            with temp.open('wb') as f:
                subprocess.run(['adb', 'exec-out', 'su', '-c', 'dd if=' + device + ' bs=1048576 2>/dev/null'], stdout=f, check=True)
            if temp.stat().st_size != size or hashlib.sha256(temp.read_bytes()).hexdigest() != remote:
                raise SystemExit('Backup verification FAILED: ' + name)
            temp.replace(target)
        records.append(dict(partition=name, size=size, sha256=remote))
        (OUT / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
        (OUT / 'SHA256SUMS').write_text(''.join(r['sha256'] + '  ' + r['partition'] + '.img\n' for r in records))
        print(f'VERIFIED {name}: {size} bytes {remote}', flush=True)

if __name__ == '__main__':
    main()
