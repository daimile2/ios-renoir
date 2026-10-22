#!/bin/bash
# Build a local 0085+ phone image (ID/timezone options require 0086+, touch power requires 0087+, GPI probe requires 0089+, allocator requires 0090+, DMA NOP requires 0093+). Never accesses or flashes the phone.
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
if [[ $# != 2 ]]; then
    echo "Usage: $0 KERNEL OUTPUT_DIR (0085+ kernel required)" >&2
    exit 2
fi
kernel_path=$(realpath -- "$1")
output_dir=$(realpath -m -- "$2")
[[ -f "$kernel_path" ]] || { echo "Kernel missing" >&2; exit 1; }
[[ ! -e "$output_dir" ]] || { echo "Use a new output directory" >&2; exit 1; }
export PATH="$project_dir/toolchain/bin:$PATH"
mkdir -p "$output_dir"
python3 src/tools/mkadt-renoir.py "$output_dir/renoir.adt"
python3 - "$output_dir/cmdline.txt" <<'PY'
from pathlib import Path
import os, sys
cal = Path('artifacts/time-reference/ats_2.bin').read_bytes()
if len(cal) != 8:
    raise SystemExit('RTC calibration must be eight bytes')
offset = int.from_bytes(cal, 'little')
if not 1577836800000 <= offset <= 4102444800000:
    raise SystemExit('Unexpected calibration range; inspect RTC provenance')
base = Path('artifacts/xnu-renoir-0084/phone-keys-10hz-v2/cmdline.txt').read_text().strip()
args = base + f' renoirrtc=1 rtc_offset_ms={offset} renoirspiprobe=1'
if os.environ.get('RENOIR_SPI_ID') == '1':
    args += ' renoirspiid=1'
if os.environ.get('RENOIR_SHANGHAI') == '1':
    args += ' renoirshanghai=1'
if os.environ.get('RENOIR_TOUCH_POWER') == '1':
    # Leave room for the next hardware flag; keep keys/RTC/root settings.
    args = ' '.join('sweetsample=-' if a.startswith('sweetsample=') else a for a in args.split())
    args += ' renoirpower=1'
if os.environ.get('RENOIR_GPI_PROBE') == '1':
    args += ' renoirgpiprobe=1'
if os.environ.get('RENOIR_GPI_ALLOC') == '1':
    if os.environ.get('RENOIR_GPI_PROBE') != '1':
        raise SystemExit('GPI allocator requires GPI probe')
    args += ' renoirgpialloc=1'
if os.environ.get('RENOIR_GPI_DMA') == '1':
    if os.environ.get('RENOIR_GPI_ALLOC') != '1':
        raise SystemExit('DMA NOP requires GPI allocator')
    args += ' renoirgpidma=1'
if os.environ.get('RENOIR_GPI_LOCK') in ('1', '2'):
    if os.environ.get('RENOIR_GPI_DMA') != '1':
        raise SystemExit('GPI LOCK requires DMA test')
    args += ' gpilock=' + os.environ['RENOIR_GPI_LOCK']
if os.environ.get('RENOIR_GPIO_SPI') == '1':
    if os.environ.get('RENOIR_TOUCH_POWER') != '1' or os.environ.get('RENOIR_SPI_ID') != '1':
        raise SystemExit('GPIO SPI requires touch power and SPI ID options')
    if any(os.environ.get(k) == '1' for k in ('RENOIR_GPI_PROBE', 'RENOIR_GPI_ALLOC', 'RENOIR_GPI_DMA')) or os.environ.get('RENOIR_GPI_LOCK') in ('1', '2'):
        raise SystemExit('GPIO SPI image must omit GPI options')
    args += ' bbspi=1'
if len(args.encode()) >= 608:
    raise SystemExit('Boot args exceed shim limit')
Path(sys.argv[1]).write_text(args + '\n')
PY
python3 src/tools/mkpayload.py "$kernel_path" "$output_dir/renoir.adt" \
    "$output_dir/payload.bin" --cmdline "$(cat "$output_dir/cmdline.txt")"
SHIM_MODE=full DTB_PATH="$project_dir/dtb/vendor-boot/vendor_boot_a.img-dtb" \
    bash src/shim/build.sh "$output_dir/payload.bin"
cp src/shim/out/shim-boot.img "$output_dir/shim-boot.img"
python3 src/tools/unpack_bootv2.py "$output_dir/shim-boot.img" "$output_dir/unpacked"
cmp "$output_dir/payload.bin" "$output_dir/unpacked/ramdisk"
cmp dtb/vendor-boot/vendor_boot_a.img-dtb "$output_dir/unpacked/dtb"
python3 - "$kernel_path" "$output_dir" <<'PY'
from pathlib import Path
import hashlib, json, subprocess, sys
kernel, out = Path(sys.argv[1]), Path(sys.argv[2])
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
d = dict(kernel_sha256=sha(kernel), image_sha256=sha(out/'shim-boot.img'),
         source_checkout=subprocess.check_output(['git','-C','src','rev-parse','HEAD'],text=True).strip(),
         cmdline=(out/'cmdline.txt').read_text().strip(), root_reflash=False,
         phone_result='not booted', features=['calibrated RTC','GENI SPI observation'],
         touch_events=False)
d['spi_chip_id_enabled'] = 'renoirspiid=1' in d['cmdline']
d['timezone_repair_enabled'] = 'renoirshanghai=1' in d['cmdline']
d['touch_power_enabled'] = 'renoirpower=1' in d['cmdline']
d['gpi_smmu_probe_enabled'] = 'renoirgpiprobe=1' in d['cmdline']
d['gpi_command_allocator_enabled'] = 'renoirgpialloc=1' in d['cmdline']
d['gpio_spi_id_enabled'] = 'bbspi=1' in d['cmdline']
d['gpi_spi_id_trial_enabled'] = 'gpilock=2' in d['cmdline']
d['gpi_lock_unlock_enabled'] = any(a in d['cmdline'] for a in ('gpilock=1', 'gpilock=2'))
d['gpi_dma_nop_enabled'] = 'renoirgpidma=1' in d['cmdline']
(out/'manifest.json').write_text(json.dumps(d,indent=2)+'\n')
print('Built and unpack-verified local image:', out/'shim-boot.img')
print('No device operation performed; touch events are not implemented.')
PY
