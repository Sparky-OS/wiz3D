#!/bin/bash
# Run inside the installed-package container as an ordinary user: the installed
# wiz3d-run against the installed KWin (kwin_wayland --virtual --xwayland).
# Usage: test-kwin.sh NEW-EVIDENCE-DIRECTORY
set -u
D=$(realpath -m "${1:?Usage: test-kwin.sh NEW-EVIDENCE-DIRECTORY}")
[ ! -e "$D" ] || { echo "Refusing to reuse $D" >&2; exit 2; }
mkdir -p "$D"
RUN=${WIZ3D_TEST_RUN:-/usr/bin/wiz3d-run}
HERE=$(dirname "$(realpath "$0")")
export XDG_RUNTIME_DIR=$D/runtime
mkdir -m 700 "$XDG_RUNTIME_DIR"
export LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=4 QT_QPA_PLATFORM=offscreen
dbus-run-session -- bash -s "$D" "$RUN" "$HERE" <<'TESTS'
D=$1; RUN=$2; HERE=$3
getcap "$(command -v kwin_wayland)" > "$D/kwin-capability.txt" 2>&1
kwin_wayland --virtual --xwayland --socket=wiz3d-kwin --width 1920 --height 1080 > "$D/kwin.log" 2>&1 &
KWIN=$!
for i in $(seq 1 120); do [ -S "$XDG_RUNTIME_DIR/wiz3d-kwin" ] && [ -S /tmp/.X11-unix/X0 ] && break; sleep .25; done
export DISPLAY=:0
status=0
fail() { echo "FAIL: $*"; status=1; }
xprop -root _KDE_NET_WM_STEREO_CONTENT_SUPPORTED > "$D/root-support.txt" 2>&1
cat "$D/root-support.txt"
grep -q '= 3$' "$D/root-support.txt" && echo "PASS: KWin announces declaration version 3" || fail "root property is not 3"
# Version 3: declared, KWin doubles the one-view window, wiz3d keeps its size.
"$RUN" -- python3 "$HERE/test-kwin-surrogate.py" 4 > "$D/enabled.log" 2>&1
cat "$D/enabled.log"
grep -q 'wiz3d-run: declared .*full SBS' "$D/enabled.log" && echo "PASS: wiz3d-run declared the window through libstereo-declare" || fail "no declaration"
grep -q 'SURROGATE: size=1600x600 declared=\[3\] enable=1 kwin_doubles=1' "$D/enabled.log" && echo "PASS: one-view 800x600 window doubled by KWin to 1600x600, declared 3, launcher told the plug-in" || fail "enabled result"
# Disabled: no declaration, no doubling.
"$RUN" --disable-3d -- python3 "$HERE/test-kwin-surrogate.py" 3 > "$D/disabled.log" 2>&1
cat "$D/disabled.log"
grep -q 'SURROGATE: size=800x600 declared=None enable=0 kwin_doubles=None' "$D/disabled.log" && echo "PASS: disabled state: undeclared, 800x600 untouched" || fail "disabled result"
kill $KWIN; wait $KWIN 2>/dev/null
exit $status
TESTS
