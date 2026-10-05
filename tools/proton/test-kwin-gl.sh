#!/bin/bash
# Run inside the installed-package container as an ordinary user: a Windows
# OpenGL program with a PFD_STEREO pixel format (red in GL_BACK_LEFT, green in
# GL_BACK_RIGHT) under Wine on the installed KWin, version 3, checked with
# KWin's own screen capture. WIZ3D_TEST_ARCH=x86 runs the 32-bit program in WoW64.
# Usage: test-kwin-gl.sh NEW-EVIDENCE-DIRECTORY
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
D=$(realpath -m "${1:?Usage: test-kwin-gl.sh NEW-EVIDENCE-DIRECTORY}")
[ ! -e "$D" ] || { echo "Refusing to reuse $D" >&2; exit 2; }
mkdir -p "$D/game"
XDG_RUNTIME_DIR=$(mktemp -d /tmp/wiz3d-rt.XXXXXX)
export XDG_RUNTIME_DIR
export LIBGL_DEBUG=verbose LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=4 QT_QPA_PLATFORM=offscreen KWIN_SCREENSHOT_NO_PERMISSION_CHECKS=1
export WINEPREFIX=$D/prefix WINEARCH=win64 WINEDEBUG=${WIZ3D_TEST_WINEDEBUG:--all}
if [ "${WIZ3D_TEST_ARCH:-x64}" = x86 ]; then CC=i686-w64-mingw32-gcc; else CC=x86_64-w64-mingw32-gcc; fi
"$CC" -Wall -Wextra -O2 "$REPO/tools/run-wine/probe/glstereo.c" -o "$D/game/glstereo.exe" -lopengl32 -lgdi32 || exit 1
dbus-run-session -- bash -s "$D" "$REPO" <<'TESTS'
D=$1
status=0
fail() { echo "FAIL: $*"; status=1; }
kwin_wayland --virtual --xwayland --socket=wiz3d-kwin --width 1920 --height 1080 > "$D/kwin.log" 2>&1 &
KWIN=$!
for i in $(seq 1 120); do [ -S "$XDG_RUNTIME_DIR/wiz3d-kwin" ] && [ -S /tmp/.X11-unix/X0 ] && break; sleep .25; done
export DISPLAY=:0
xprop -root _KDE_NET_WM_STEREO_CONTENT_SUPPORTED | tee "$D/root-support.txt"
WINEDLLOVERRIDES=mscoree,mshtml= wineboot -u > "$D/wineboot.log" 2>&1
wineserver -w
cd "$D/game"
wine glstereo.exe 25 ${WIZ3D_TEST_GLMODE:-} > "$D/glstereo.log" 2>&1 &
for i in $(seq 1 120); do grep -q 'GLSTEREO: ready\|GLSTEREO FAIL' "$D/glstereo.log" && break; sleep .5; done
cat "$D/glstereo.log"
sleep 1
xwininfo -root -tree > "$D/tree.txt"
WID=$(awk '/"glstereo"/ {print $1; exit}' "$D/tree.txt")
grep -A3 '"glstereo"' "$D/tree.txt" | head -4
xprop -id "$WID" _KDE_NET_WM_STEREO_CONTENT > "$D/declaration-whole.txt" 2>&1
cat "$D/declaration-whole.txt"
/opt/wiz3d-capture/kwin-capture --screen > "$D/capture.txt" 2>&1
cat "$D/capture.txt"
if [ "${WIZ3D_TEST_GLMODE:-}" = mono ]; then
    grep -q 'STEREO_CONTENT(CARDINAL) = [1-9]' "$D/declaration-whole.txt" && fail "mono program is declared" || echo "PASS: mono program is undeclared"
    python3 - "$D/capture.txt" <<'PY' || status=1
import re, sys
t = open(sys.argv[1]).read()
red = re.search(r'red_at\((\d+),(\d+)\)', t)
green = re.search(r'green_at\((\d+),(\d+)\)', t)
ok = red and not green
print('PASS: red only, green absent (red at x=%s)' % red.group(1) if ok else 'FAIL: red %s green %s' % (red, green))
sys.exit(0 if ok else 1)
PY
    wineserver -k
    kill $KWIN; wait $KWIN 2>/dev/null
    exit $status
fi
grep -q 'STEREO_CONTENT(CARDINAL) = 3' "$D/declaration-whole.txt" && echo "PASS: whole window carries the declaration" || fail "no declaration on the whole window"
python3 - "$D/capture.txt" <<'PY' || status=1
import re, sys
t = open(sys.argv[1]).read()
red = re.search(r'red_at\((\d+),(\d+)\)', t)
green = re.search(r'green_at\((\d+),(\d+)\)', t)
assert red and green, 'no red or green in the capture'
print('PASS: red at x=%s, green at x=%s' % (red.group(1), green.group(1)) if int(red.group(1)) < int(green.group(1)) else 'FAIL: red not left of green')
sys.exit(0 if int(red.group(1)) < int(green.group(1)) else 1)
PY
wineserver -k
kill $KWIN; wait $KWIN 2>/dev/null
exit $status
TESTS
