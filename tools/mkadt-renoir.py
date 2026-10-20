#!/usr/bin/env python3
"""Renoir ADT from the 2026-10-20 live FDT; retain SWEET driver match names."""
import argparse
from pathlib import Path
import mkadt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--qemu', action='store_true')
    args = parser.parse_args()
    mkadt.FB, mkadt.FB_SIZE = 0xe1000000, 0x02300000
    mkadt.VTIMER_INTID = 27
    # The live memory bank is 0x180000000+4GiB; its top 2GiB have no
    # reserved subregions in Android's iomem. XPU access is not yet measured.
    mkadt.HIGH_PHYS_BASE, mkadt.HIGH_MEM_SIZE = 0x200000000, 0x80000000
    root = mkadt.build(qemu=args.qemu, highmem=not args.qemu)
    # Keep xiaomi,sweet for existing IOKit matching, add the actual SoC.
    root.props = [(k, flags, value.replace(b'qcom,sm7150\0', b'qcom,sm7350\0'))
                  for k, flags, value in root.props]
    blob = mkadt.adt.serialize(root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(blob)
    print(f'{args.out}: {len(blob)} bytes; XPU access to the phone RAM candidate remains unverified')

if __name__ == '__main__':
    main()
