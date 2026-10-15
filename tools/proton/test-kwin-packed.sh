#!/bin/bash
# Run inside a container with the stereo Wine, the stereo DXVK (2.7.1-4+stereo3d3 or newer: dxvk.stereoInput) and the
# package installed, as an ordinary user, on the installed KWin: a game that draws both eyes itself, packed as the
# games with a 3D mode of their own draw (probe-packed), goes through "wiz3d-launch --native-stereo LAYOUT" and
# comes out as full side by side, left eye first, each eye at full size, declared and doubled by KWin.
# Every packing and both eye orders; the control (3D off) shows the packed picture as it is; a packing declared with
# the wrong eye order fails the check, so the check can fail.
# Usage: test-kwin-packed.sh NEW-EVIDENCE-DIRECTORY
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$(realpath -m "${1:?Usage: test-kwin-packed.sh NEW-EVIDENCE-DIRECTORY}")
[ ! -e "$OUT" ] || { echo "Refusing to reuse $OUT" >&2; exit 2; }
mkdir -p "$OUT"
LAUNCH=${WIZ3D_TEST_LAUNCH:-/usr/bin/wiz3d-launch}
XDG_RUNTIME_DIR=$(mktemp -d /tmp/wiz3d-rt.XXXXXX)
export XDG_RUNTIME_DIR
export LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=4 QT_QPA_PLATFORM=offscreen
export VK_ICD_FILENAMES=${VK_ICD_FILENAMES:-$(ls /usr/share/vulkan/icd.d/lvp_icd*.json | head -1)}
export WINEDEBUG=${WIZ3D_TEST_WINEDEBUG:--all} WIZ3D_WINETRICKS=0
export WIZ3D_TEST_WINEDEBUG
dpkg-query -W -f='${Package} ${Version}\n' mesa-vulkan-drivers kwin-wayland dxvk-wine64 dxvk-wine32 wine64 wiz3d 2>/dev/null > "$OUT/versions.txt"
cat "$OUT/versions.txt"
x86_64-w64-mingw32-gcc -Wall -Wextra -O2 "$REPO/tools/run-wine/probe-packed/probe_packed.c" -o "$OUT/probe_packed.exe" -ld3d9 || exit 1
dbus-run-session -- bash -s "$OUT" "$REPO" "$LAUNCH" <<'TESTS'
OUT=$1; REPO=$2; LAUNCH=$3
kwin_wayland --virtual --xwayland --socket=wiz3d-kwin --width 3400 --height 1200 > "$OUT/kwin.log" 2>&1 &
KWIN=$!
for i in $(seq 1 120); do [ -S "$XDG_RUNTIME_DIR/wiz3d-kwin" ] && [ -S /tmp/.X11-unix/X0 ] && break; sleep .25; done
export DISPLAY=:0
xprop -root _KDE_NET_WM_STEREO_CONTENT_SUPPORTED | tee "$OUT/root-support.txt"
grep -q '= 3$' "$OUT/root-support.txt" || { echo "FAIL: KWin does not announce version 3"; kill $KWIN; exit 1; }
export WINEPREFIX=$OUT/prefix
"$LAUNCH" --disable-3d -- wine cmd /c exit > "$OUT/prefix.log" 2>&1 || { echo "FAIL: the prefix"; tail -5 "$OUT/prefix.log"; kill $KWIN; exit 1; }
wineserver -w
status=0
run_case() {  # run_case NAME PACKING RIGHT-FIRST(0/1) LAUNCH-ARGS... ; env PROBE_* for the probe
    local name=$1 packing=$2 right=$3; shift 3
    local D=$OUT/$name
    mkdir -p "$D/game"
    cp "$OUT/probe_packed.exe" "$D/game/"
    echo "=== $name ==="
    ( cd "$D/game" && env PROBE_PACKING=$packing ${right:+PROBE_RIGHT_FIRST=1} timeout 90 "$LAUNCH" "$@" -- wine probe_packed.exe > "$D/probe.log" 2>&1 ) &
    local pid=$!
    for i in $(seq 1 60); do grep -q 'PROBE: ready' "$D/probe.log" && break; kill -0 $pid 2>/dev/null || break; sleep 1; done
    grep -q 'PROBE: ready' "$D/probe.log" || { echo "FAIL: $name: the probe did not get ready"; tail -5 "$D/probe.log"; touch "$D/game/stop.flag"; wait $pid; return 1; }
    sleep 2
    local wid
    wid=$(xwininfo -root -tree | awk '/wiz3dpacked-x/ {print $1; exit}')
    xprop -id "$wid" _KDE_NET_WM_STEREO_CONTENT > "$D/declaration.txt" 2>&1
    xwininfo -id "$wid" -tree > "$D/window.txt" 2>&1
    xwd -id "$wid" -silent -out "$D/frame.xwd"
    touch "$D/game/stop.flag"
    wait $pid
    echo "exit=$?" >> "$D/probe.log"
    grep -E 'PROBE|declared|Stereo input|stereoInput|err:' "$D/probe.log" | head -6
}
check() {  # check NAME ARGS... -> PASS/FAIL line
    local name=$1; shift
    if python3 "$REPO/tools/run-wine/check-packed.py" "$OUT/$name/frame.xwd" "$@" > "$OUT/$name/measurements.txt" 2>&1; then
        echo "PASS: $name: $(cat "$OUT/$name/measurements.txt")"
    else
        echo "FAIL: $name: $(tail -1 "$OUT/$name/measurements.txt")"; status=1
    fi
}
PACKINGS=${WIZ3D_TEST_PACKINGS:-sideBySide topAndBottom rows columns checkerboard frameSequential}
for packing in $PACKINGS; do
    run_case "$packing" "$packing" "" --native-stereo "$packing"
    grep -q '^_KDE_NET_WM_STEREO_CONTENT(CARDINAL) = 3$' "$OUT/$packing/declaration.txt" || { echo "FAIL: $packing: not declared"; status=1; }
    check "$packing"
    run_case "$packing-right-first" "$packing" 1 --native-stereo "$packing" --right-eye-first
    check "$packing-right-first"
done
for packing in ${WIZ3D_TEST_ANAGLYPHS-anaglyphRedCyan anaglyphGreenMagenta anaglyphAmberBlue}; do
    run_case "$packing" "$packing" "" --native-stereo "$packing"
    check "$packing" --anaglyph
done
# The check can fail: a right-first picture declared as left first comes out with the eyes swapped.
run_case swapped-negative sideBySide 1 --native-stereo sideBySide
if python3 "$REPO/tools/run-wine/check-packed.py" "$OUT/swapped-negative/frame.xwd" > "$OUT/swapped-negative/measurements.txt" 2>&1; then
    echo "FAIL: swapped-negative: the check passed a picture with the eyes the wrong way round"; status=1
else
    echo "PASS: swapped-negative: rejected ($(tail -1 "$OUT/swapped-negative/measurements.txt" | cut -c1-80))"
fi
# The control: without stereo the window keeps its size and shows the packed picture as the game drew it.
run_case control sideBySide "" --disable-3d
check control --packed
grep -q '_KDE_NET_WM_STEREO_CONTENT(CARDINAL)' "$OUT/control/declaration.txt" && { echo "FAIL: control: declared"; status=1; }
rm -rf "$OUT/prefix"
kill $KWIN; wait $KWIN 2>/dev/null
exit $status
TESTS
