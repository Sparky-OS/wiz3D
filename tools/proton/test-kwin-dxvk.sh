#!/bin/bash
# Run inside the installed-package container as an ordinary user: the full-SBS
# suite through Wine and DXVK on the installed KWin (declaration version 3: the
# game's window keeps one eye's size, KWin doubles it). Needs Mesa
# 26.1.6-1+stereo3d4 or newer (the Vulkan surface reports the whole window).
# Usage: test-kwin-dxvk.sh NEW-EVIDENCE-DIRECTORY
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$(realpath -m "${1:?Usage: test-kwin-dxvk.sh NEW-EVIDENCE-DIRECTORY}")
[ ! -e "$OUT" ] || { echo "Refusing to reuse $OUT" >&2; exit 2; }
mkdir -p "$OUT"
# A short path: socket names of the compositor and Xwayland must fit in 108 bytes.
XDG_RUNTIME_DIR=$(mktemp -d /tmp/wiz3d-rt.XXXXXX)
export XDG_RUNTIME_DIR
export LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=4 QT_QPA_PLATFORM=offscreen
export WIZ3D_TEST_DLL_DIR=${WIZ3D_TEST_DLL_DIR:-/usr/lib/wiz3d/${WIZ3D_TEST_ARCH:-x64}} WIZ3D_TEST_RUN=${WIZ3D_TEST_RUN:-/usr/bin/wiz3d-run}
export VK_ICD_FILENAMES=${VK_ICD_FILENAMES:-$(ls /usr/share/vulkan/icd.d/lvp_icd*.json | head -1)}
dpkg-query -W -f='${Package} ${Version}\n' mesa-vulkan-drivers kwin-wayland > "$OUT/versions.txt"
cat "$OUT/versions.txt"
dbus-run-session -- bash -s "$OUT" "$REPO" <<'TESTS'
OUT=$1; REPO=$2
kwin_wayland --virtual --xwayland --socket=wiz3d-kwin --width 3400 --height 1200 > "$OUT/kwin.log" 2>&1 &
KWIN=$!
for i in $(seq 1 120); do [ -S "$XDG_RUNTIME_DIR/wiz3d-kwin" ] && [ -S /tmp/.X11-unix/X0 ] && break; sleep .25; done
export WIZ3D_TEST_DISPLAY=:0
DISPLAY=:0 xprop -root _KDE_NET_WM_STEREO_CONTENT_SUPPORTED | tee "$OUT/root-support.txt"
grep -q '= 3$' "$OUT/root-support.txt" || { echo "FAIL: KWin does not announce version 3"; kill $KWIN; exit 1; }
status=0
for CASE in normal low high reset reset-width disabled fullscreen swapped; do
    export WIZ3D_TEST_LAUNCHER=1
    unset PROBE_WIDTH PROBE_HEIGHT PROBE_RESET PROBE_RESET_AUTO PROBE_RESET_WIDTH_ONLY PROBE_FULLSCREEN WIZ3D_TEST_SWAP
    case $CASE in
        low) export PROBE_WIDTH=400 PROBE_HEIGHT=300;;
        high) export PROBE_WIDTH=1200 PROBE_HEIGHT=900;;
        reset) export PROBE_RESET=1 PROBE_RESET_AUTO=1;;
        reset-width) export PROBE_RESET=1 PROBE_RESET_WIDTH_ONLY=1;;
        disabled) export WIZ3D_TEST_LAUNCHER=2;;
        fullscreen) export PROBE_FULLSCREEN=1;;
        swapped) export WIZ3D_TEST_SWAP=1;;
    esac
    echo "=== $CASE ==="
    bash "$REPO/tools/run-wine/run-test.sh" "$REPO" "$OUT/$CASE" full .16 2>&1 | tee "$OUT/$CASE.log"
    [ "${PIPESTATUS[0]}" = 0 ] || status=1
    rm -rf "$OUT/$CASE/prefix"
done
(cd "$REPO/tools/run-wine" && python3 check-negative.py "$OUT/normal/frame.xwd" full) 2>&1 | tee "$OUT/negative.log"
[ "${PIPESTATUS[0]}" = 0 ] || status=1
kill $KWIN; wait $KWIN 2>/dev/null
exit $status
TESTS
