#!/usr/bin/env python3
"""Verify the local HFS+ image and sparse expansion without writing another image."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'artifacts/ios16-root-20H392-v1.img'
SPARSE = RAW.with_suffix('.simg')
REPORT = ROOT / 'artifacts/ios16-root-20H392-v1-validation.json'
BUFFER = 4 * 1024 * 1024


def read_exact(stream, count):
    data = stream.read(count)
    if len(data) != count:
        raise ValueError('Truncated sparse image')
    return data


def verify():
    expected = {}
    for line in RAW.with_suffix('.img.sha256').read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        expected[Path(filename).name] = digest
    raw_hash = hashlib.sha256()
    with RAW.open('rb') as source:
        while data := source.read(BUFFER):
            raw_hash.update(data)
        source.seek(1024)
        header = source.read(512)
    signature, version = struct.unpack_from('>HH', header)
    block_size, blocks = struct.unpack_from('>II', header, 40)
    assert signature == 0x4858 and version == 5, 'Expected case-sensitive HFS+'
    assert block_size * blocks == RAW.stat().st_size
    assert raw_hash.hexdigest() == expected[RAW.name], 'Raw image hash mismatch'
    sparse_hash, expanded_hash = hashlib.sha256(), hashlib.sha256()
    with SPARSE.open('rb') as source:
        def take(count):
            data = read_exact(source, count)
            sparse_hash.update(data)
            return data
        magic, major, minor, fh, ch, bs, total, chunks, checksum = struct.unpack('<I4H4I', take(28))
        assert magic == 0xed26ff3a and major == 1 and fh >= 28 and ch >= 12
        assert bs > 0 and bs % 4 == 0
        take(fh - 28)
        expanded = 0
        for _ in range(chunks):
            kind, _, count, size = struct.unpack('<2H2I', take(12))
            take(ch - 12)
            length = count * bs
            if kind == 0xcac1:
                assert size == ch + length
                remaining = length
                while remaining:
                    part = take(min(BUFFER, remaining))
                    expanded_hash.update(part)
                    remaining -= len(part)
            elif kind in (0xcac2, 0xcac3):
                assert size == ch + (4 if kind == 0xcac2 else 0)
                pattern = take(4) if kind == 0xcac2 else b'\0' * 4
                fill = pattern * (BUFFER // 4)
                remaining = length
                while remaining:
                    part = fill[:min(BUFFER, remaining)]
                    expanded_hash.update(part)
                    remaining -= len(part)
            elif kind == 0xcac4:
                assert count == 0 and size == ch + 4
                take(4)
            else:
                raise ValueError(f'Unknown sparse chunk type {kind:#x}')
            expanded += length
        assert source.read(1) == b'', 'Trailing sparse bytes'
    assert expanded == total * bs == RAW.stat().st_size
    assert sparse_hash.hexdigest() == expected[SPARSE.name], 'Sparse image hash mismatch'
    assert expanded_hash.digest() == raw_hash.digest(), 'Sparse expansion differs from raw image'
    report = dict(raw=str(RAW.relative_to(ROOT)), sparse=str(SPARSE.relative_to(ROOT)),
                  raw_sha256=raw_hash.hexdigest(), sparse_sha256=sparse_hash.hexdigest(),
                  sparse_expanded_sha256=expanded_hash.hexdigest(),
                  expanded_bytes=expanded, sparse_bytes=SPARSE.stat().st_size,
                  hfs_signature='HX', hfs_version=version, hfs_block_size=block_size,
                  sparse_chunks=chunks, sparse_expansion_matches_raw=True,
                  note='Content integrity verified; successful iOS runtime boot is not implied.')
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    verify()
