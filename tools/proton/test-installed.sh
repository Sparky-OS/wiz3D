#!/bin/bash
# Run inside the installed-package container as an ordinary user: the existing
# full-SBS suite against /usr/lib/wiz3d and /usr/bin/wiz3d-run, in a private Xvfb
# whose root property announces declaration version ${WIZ3D_TEST_SUPPORT:-2}
# (version 2: wiz3D doubles the window itself).
# Usage: test-installed.sh NEW-EVIDENCE-DIRECTORY
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$(realpath -m "${1:?Usage: test-installed.sh NEW-EVIDENCE-DIRECTORY}")
[ ! -e "$OUT" ] || { echo "Refusing to reuse $OUT" >&2; exit 2; }
mkdir -p "$OUT"
export WIZ3D_TEST_DLL_DIR=${WIZ3D_TEST_DLL_DIR:-/usr/lib/wiz3d/${WIZ3D_TEST_ARCH:-x64}} WIZ3D_TEST_RUN=${WIZ3D_TEST_RUN:-/usr/bin/wiz3d-run}
export WIZ3D_TEST_SUPPORT=${WIZ3D_TEST_SUPPORT:-2}
export VK_ICD_FILENAMES=${VK_ICD_FILENAMES:-$(ls /usr/share/vulkan/icd.d/lvp_icd*.json | head -1)}
RUN_DEFAULT=$WIZ3D_TEST_RUN
for CASE in normal low high reset reset-width disabled fullscreen swapped prefix launch; do
    export WIZ3D_TEST_LAUNCHER=1 WIZ3D_TEST_RUN=$RUN_DEFAULT
    unset PROBE_WIDTH PROBE_HEIGHT PROBE_RESET PROBE_RESET_AUTO PROBE_RESET_WIDTH_ONLY PROBE_FULLSCREEN WIZ3D_TEST_SWAP WIZ3D_TEST_PREFIX_INSTALL
    case $CASE in
        low) export PROBE_WIDTH=400 PROBE_HEIGHT=300;;
        high) export PROBE_WIDTH=1200 PROBE_HEIGHT=900;;
        reset) export PROBE_RESET=1 PROBE_RESET_AUTO=1;;
        reset-width) export PROBE_RESET=1 PROBE_RESET_WIDTH_ONLY=1;;
        disabled) export WIZ3D_TEST_LAUNCHER=2;;
        fullscreen) export PROBE_FULLSCREEN=1;;
        swapped) export WIZ3D_TEST_SWAP=1;;
        prefix) export WIZ3D_TEST_PREFIX_INSTALL=1;;
        launch) export WIZ3D_TEST_PREFIX_INSTALL=2 WIZ3D_TEST_RUN=${WIZ3D_TEST_LAUNCH:-/usr/bin/wiz3d-launch};;
    esac
    echo "=== $CASE ==="
    bash "$REPO/tools/run-wine/run-test.sh" "$REPO" "$OUT/$CASE" full .16 2>&1 | tee "$OUT/$CASE.log"
    rm -rf "$OUT/$CASE/prefix"
done
export WIZ3D_TEST_RUN=$RUN_DEFAULT
echo "=== negative controls on the installed full frame ==="
(cd "$REPO/tools/run-wine" && python3 check-negative.py "$OUT/normal/frame.xwd" full) | tee "$OUT/negative.log"
echo "=== wiz3d-launch on a made-up prefix ==="
WIZ3D_TEST_LAUNCH=${WIZ3D_TEST_LAUNCH:-/usr/bin/wiz3d-launch} python3 -I "$REPO/tools/proton/test-launch.py" 2>&1 | tee "$OUT/launch.log"
echo "=== launcher ==="
Xvfb :98 -noreset -screen 0 1800x900x24 >"$OUT/launcher-xvfb.log" 2>&1 &
XVFB=$!
sleep 1
DISPLAY=:98 timeout 60 python3 -u "$REPO/tools/proton/test-launcher.py" 2>&1 | tee "$OUT/launcher.log"
kill $XVFB
