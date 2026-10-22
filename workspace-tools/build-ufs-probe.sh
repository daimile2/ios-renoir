#!/bin/bash
set -euo pipefail
PROJECT_ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$PROJECT_ROOT/toolchain/bin:$PATH"
export DTB_PATH="$PROJECT_ROOT/dtb/vendor-boot/vendor_boot_a.img-dtb"
export SHIM_MODE=ufs
VERSION=${1:-v2}
[[ $VERSION =~ ^v[0-9]+$ ]] || { echo "Expected version v1, v2, ..." >&2; exit 1; }
DESTINATION="$PROJECT_ROOT/artifacts/shim-ufs-$VERSION"
[[ ! -e "$DESTINATION" ]] || { echo "Preserving existing artifact: $DESTINATION" >&2; exit 1; }
bash "$PROJECT_ROOT/src/shim/build.sh"
mkdir -p "$DESTINATION"
cp "$PROJECT_ROOT/src/shim/out/"{Image,shim.elf,shim-boot.img} "$DESTINATION/"
(cd "$DESTINATION" && sha256sum Image shim.elf shim-boot.img > SHA256SUMS)
