#!/bin/bash
# Build local image files only. This script never accesses the phone.
set -euo pipefail
PROJECT_ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$PROJECT_ROOT/toolchain/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export TMPDIR="$PROJECT_ROOT/artifacts/tmp"
IMAGE_PATH="$PROJECT_ROOT/artifacts/ios16-root-20H392-v1.img"
SPARSE_PATH="$PROJECT_ROOT/artifacts/ios16-root-20H392-v1.simg"
mkdir -p "$TMPDIR" "$PROJECT_ROOT/logs"
for utility in apfs-fuse mkfs.hfsplus fsck.hfsplus rsync img2simg; do
    command -v "$utility" >/dev/null || { echo "Missing utility: $utility" >&2; exit 1; }
done
# Capture through a file: a failed verification must not be hidden by a
# process substitution or by mapfile's successful exit code.
python3 "$PROJECT_ROOT/tools/verify-ios.py" --paths > "$TMPDIR/verified-image-paths.txt"
mapfile -t COMPONENTS < "$TMPDIR/verified-image-paths.txt"
[[ ${#COMPONENTS[@]} == 3 ]] || exit 1
if [[ ${1:-} == --check ]]; then
    echo "Local image prerequisites and component hashes verified. No image created."
    exit 0
fi
[[ $# == 0 ]] || { echo "Usage: $0 [--check]" >&2; exit 2; }
[[ $EUID == 0 ]] || { echo "Local loop mounts and owner preservation require: sudo bash tools/build-ios-root.sh" >&2; exit 1; }
[[ ! -e "$IMAGE_PATH" && ! -e "$SPARSE_PATH" ]] || { echo "Output already exists; inspect it before selecting another image version." >&2; exit 1; }
AVAILABLE_BYTES=$(df -B1 --output=avail "$PROJECT_ROOT" | tail -1 | tr -d ' ')
[[ $AVAILABLE_BYTES -ge $((24 * 1024 * 1024 * 1024)) ]] || { echo "Need at least 24 GiB free for the local raw and sparse images." >&2; exit 1; }
exec > >(tee "$PROJECT_ROOT/logs/build-ios-root-v1.log") 2>&1
bash "$PROJECT_ROOT/src/tools/mkiosroot.sh" "${COMPONENTS[@]}" "$IMAGE_PATH" 16G
MOUNT_PATH="$TMPDIR/tweak-root-v1"
mkdir -p "$MOUNT_PATH"
cleanup() {
    if mountpoint -q "$MOUNT_PATH"; then
        umount "$MOUNT_PATH" || echo "Unmount failed: $MOUNT_PATH" >&2
    fi
}
trap cleanup EXIT
mount -t hfsplus -o loop,force "$IMAGE_PATH" "$MOUNT_PATH"
python3 "$PROJECT_ROOT/src/tools/sweet-root-tweaks.py" "$MOUNT_PATH"
umount "$MOUNT_PATH"
fsck.hfsplus -f -n "$IMAGE_PATH"
img2simg "$IMAGE_PATH" "$SPARSE_PATH"
sha256sum "$IMAGE_PATH" "$SPARSE_PATH" > "$IMAGE_PATH.sha256"
if [[ ${SUDO_UID:-0} != 0 ]]; then
    chown "$SUDO_UID:$SUDO_GID" "$IMAGE_PATH" "$SPARSE_PATH" "$IMAGE_PATH.sha256"
fi
echo "Local image built. No device partition was changed."
