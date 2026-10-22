#!/bin/bash
set -euo pipefail
PROJECT_ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$PROJECT_ROOT/toolchain/bin:$PATH"
export DTB_PATH="$PROJECT_ROOT/dtb/vendor-boot/vendor_boot_a.img-dtb"
export SHIM_MODE=display
exec bash "$PROJECT_ROOT/src/shim/build.sh"
