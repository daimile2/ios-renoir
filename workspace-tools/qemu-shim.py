#!/usr/bin/env python3
"""Execute the display-only shim in QEMU and verify actual framebuffer stores."""
import importlib.util
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'qemu-shim-v1'
spec = importlib.util.spec_from_file_location('qemu_sweet', ROOT / 'src/tools/qemu-sweet.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=ROOT / 'artifacts/shim-v1/Image')
    parser.add_argument('--outdir', type=Path, default=OUT)
    parser.add_argument('--expect', default='renoir display probe v1')
    args = parser.parse_args()
    outdir = args.outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    mon = outdir / 'mon.sock'
    mon.unlink(missing_ok=True)
    with (outdir / 'qemu.log').open('w') as log:
        proc = subprocess.Popen(['qemu-system-aarch64', '-M', 'virt,gic-version=3',
            '-cpu', 'cortex-a76', '-m', '4G', '-display', 'none', '-serial', 'none',
            '-qmp', f'unix:{mon},server=on,wait=off',
            '-kernel', str(args.image.resolve())], stdout=log, stderr=log)
        try:
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError((outdir / 'qemu.log').read_text())
                if mon.exists():
                    break
                time.sleep(.1)
            time.sleep(3)
            result = q.qmp(str(mon), 'stop', 'info registers',
                pmemsave=(0xe1000000, 1080 * 2400 * 4, str(outdir / 'fb.raw')))
            (outdir / 'regs.txt').write_text('\n'.join(result))
            raw = (outdir / 'fb.raw').read_bytes()
            q.write_png(str(outdir / 'fb.png'), raw)
            font = bytes(int(value, 16) for value in re.findall(r'0x([0-9a-fA-F]{2})', (ROOT / 'src/shim/font.h').read_text()))
            glyphs = {font[i*16:(i+1)*16]: chr(i+32) for i in range(95)}
            lines = []
            for row in range((2400-24)//48):
                line = ''
                for col in range((1080-24)//24):
                    glyph = bytearray()
                    for y in range(16):
                        bits = 0
                        for x in range(8):
                            offset = ((24+row*48+y*3)*1080+24+col*24+x*3)*4
                            pixel = raw[offset:offset+4]
                            if pixel in (b'\xff\xff\xff\xff', b'\x00\xff\xff\xff'):
                                bits |= 0x80 >> x
                        glyph.append(bits)
                    line += glyphs.get(bytes(glyph), '?')
                lines.append(line.rstrip())
            console = '\n'.join(lines).rstrip() + '\n'
            (outdir / 'fb.txt').write_text(console)
            pixels = {raw[i:i+4] for i in range(0, len(raw), 4)}
            passed = b'\x00\x00\xff\xff' in pixels and args.expect in console
            report = dict(display_stores_verified=passed, framebuffer='0xe1000000',
                unique_colors=len(pixels), limitation='QEMU does not emulate Qualcomm ABL, DSI or DSC')
            report['expected_text'] = args.expect
            report['text_verified'] = args.expect in console
            (outdir / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report))
            if not passed:
                raise SystemExit(1)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

if __name__ == '__main__':
    main()
