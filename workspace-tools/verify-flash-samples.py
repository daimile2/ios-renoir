#!/usr/bin/env python3
"""Read-only comparison of distributed, explicitly written sparse-image regions."""
import hashlib
import json
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'artifacts/ios16-root-20H392-v1.img'
SPARSE = RAW.with_suffix('.simg')
OUT = ROOT / 'artifacts/xnu-renoir-0083/phone-ios-v1/flash-readback.json'


def main():
    ranges = []
    with SPARSE.open('rb') as source:
        magic, major, _, fh, ch, bs, total, chunks, _ = struct.unpack('<I4H4I', source.read(28))
        assert magic == 0xed26ff3a and major == 1 and bs == 4096
        source.seek(fh)
        offset = 0
        for _ in range(chunks):
            kind, _, count, size = struct.unpack('<2H2I', source.read(12))
            if kind in (0xcac1, 0xcac2) and count:
                ranges.append((offset, offset + count * bs, kind))
            source.seek(size - 12, 1)
            offset += count * bs
        assert offset == total * bs
    # Ignore DONT_CARE ranges: sparse flashing does not promise their contents.
    samples = set()
    for target in [i * total * bs // 32 for i in range(33)]:
        start, end, kind = min(ranges, key=lambda r: max(r[0] - target, target - (r[1] - bs), 0))
        at = max(start, min(target // bs * bs, end - bs))
        samples.add((at, min(64 * 1024, end - at), kind))
    samples = sorted(samples)
    # HFS+ primary volume header must be part of an actual write, not a hole.
    assert any(at <= 1024 and at + size >= 1536 for at, size, _ in samples)
    commands = ['set -e'] + [
        f'dd if=/dev/block/by-name/userdata bs=4096 skip={at // bs} count={size // bs} 2>/dev/null'
        for at, size, _ in samples]
    result = subprocess.run(['adb', 'exec-out', '\n'.join(commands)], capture_output=True, check=True)
    assert len(result.stdout) == sum(size for _, size, _ in samples), 'Incomplete device readback'
    records, position = [], 0
    with RAW.open('rb') as expected:
        for at, size, kind in samples:
            expected.seek(at)
            want = expected.read(size)
            actual = result.stdout[position:position + size]
            records.append(dict(offset=at, size=size, sparse_kind=hex(kind),
                                matches=(actual == want), expected_all_zero=not any(want),
                                actual_all_zero=not any(actual),
                                expected_sha256=hashlib.sha256(want).hexdigest(),
                                actual_sha256=hashlib.sha256(actual).hexdigest()))
            position += size
    failures = [r for r in records if not r['matches']]
    report = dict(status='mismatch' if failures else 'all_samples_match', sample_count=len(records),
                  bytes_compared=position, samples=records,
                  limitation='Distributed samples only, not a full-partition hash. DONT_CARE ranges excluded.')
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    if failures:
        raise RuntimeError(f'Readback mismatches: {failures}')
    print(f'PASS: {len(records)} distributed readback samples, {position} bytes; HFS+ header included.')


if __name__ == '__main__':
    main()
