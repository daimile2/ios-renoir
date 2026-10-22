#!/usr/bin/env python3
"""Resolve console sampler addresses using the shared cache's local nlist table.

Usage: symbolicate-ios-samples.py LOG CACHE.symbols OUT [IPSW_SYM_DUMPS...]
Reads only local symbols; exported-only symbols and large symbol gaps can be unresolved.
"""
import mmap
import re
import struct
import sys


def main():
    logfile, symbols, output = sys.argv[1:4]
    text = open(logfile, errors='replace').read()
    # The kernel can truncate a long sample line before its newline.
    text = re.sub(r'(?<!\n)(SMP [^\n]*? t\d+ pc )', r'\n\1', text)
    wanted, rows = set(), []
    slide, mh = 0, 0
    for line in text.splitlines():
        m = re.match(r'(?:SMP|CRASH) (\S+?)\[\d+\].*slide (0x[0-9a-f]+) mh (0x[0-9a-f]+)', line)
        if m:
            slide, mh = int(m[2], 16), int(m[3], 16)
        if re.match(r'(?:SMP|CRASH) \S+ (?:t\d+ |pc |bt )', line):
            addresses = [int(a, 16) for a in re.findall(r'0x[0-9a-f]+', line)]
            for a in addresses:
                if 0x180000000 <= a - slide < 0x300000000:
                    wanted.add(a - slide)
            rows.append((line, addresses, slide, mh))
    targets = sorted(wanted)
    buckets, best = {}, {}
    for target in targets:
        for key in (target >> 20, (target >> 20) - 1):
            buckets.setdefault(key, []).append(target)
    with open(symbols, 'rb') as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        base = struct.unpack_from('<Q', mm, 72)[0]
        assert base > 0
        nlist_offset, count, strings_offset, strings_size, _, _ = struct.unpack_from('<6I', mm, base)
        table = memoryview(mm)[base + nlist_offset:base + nlist_offset + count * 16]
        for strx, kind, section, desc, value in struct.iter_unpack('<IBBHQ', table):
            if kind & 0xe0 or not value or strx >= strings_size:
                continue
            for target in buckets.get(value >> 20, ()):
                if value <= target and value > best.get(target, (0, 0))[0]:
                    best[target] = (value, strx)
        table.release()
        names = {}
        for target, (value, strx) in best.items():
            at = base + strings_offset + strx
            end = mm.find(b'\0', at, min(base + strings_offset + strings_size, at + 4096))
            if end >= 0:
                names[target] = (mm[at:end].decode(errors='replace'), target - value)
        # Optional per-image ipsw symaddr dumps supply exported symbols omitted
        # from the local nlist table (especially libsystem_kernel trap wrappers).
        for dump in sys.argv[4:]:
            for line in open(dump, errors='replace'):
                match = re.match(r'0x([a-f0-9]+):\s+\([^)]*\)\s+(\S+)', line)
                if not match:
                    continue
                value, name = int(match[1], 16), match[2]
                for target in buckets.get(value >> 20, ()):
                    if value <= target and value >= best.get(target, (0, 0))[0]:
                        best[target] = (value, 0)
                        names[target] = (name, target - value)
        with open(output, 'w') as out:
            out.write('# Nearest preceding local/supplied exported symbols; unsupplied exports may be omitted.\n')
            for line, addresses, slide, mh in rows:
                out.write(line + '\n')
                for address in addresses:
                    unslid = address - slide
                    if unslid in names:
                        name, delta = names[unslid]
                        out.write(f'  {address:#x} = {name} + {delta:#x}\n')
                    elif mh <= address < mh + 0x10000000 and mh:
                        out.write(f'  {address:#x} = main image {address - mh + 0x100000000:#x}\n')
    print(f'Nearest local symbols found for {len(names)}/{len(targets)} cache addresses; see {output}')


if __name__ == '__main__':
    main()
