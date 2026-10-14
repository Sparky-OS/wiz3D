#!/bin/bash
# Run inside wiz3d-wine-test. Output must be a new directory in the workspace.
set -euo pipefail
REPO=$(realpath "$1")
DLL_DIR=${WIZ3D_TEST_DLL_DIR:-$REPO/out/x64}
D=$(realpath -m "$2")
MODE=${3:-half}
SEPARATION=${4:-0.16}
LAUNCHER=${WIZ3D_TEST_LAUNCHER:-0}
LAUNCHER_BIN=${WIZ3D_TEST_RUN:-$REPO/tools/proton/wiz3d-run}
if [ "$MODE" = full ]; then export PROBE_FULL_MODE=1; fi
[ ! -e "$D" ] || { echo "Refusing to reuse evidence directory: $D" >&2; exit 2; }
PREFIX_INSTALL=${WIZ3D_TEST_PREFIX_INSTALL:-0}
mkdir -p "$D/game"
export WINEPREFIX=$D/prefix WINEARCH=win64 WINEDEBUG=+loaddll
export DISPLAY=${WIZ3D_TEST_DISPLAY:-:99} LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=4
export VK_ICD_FILENAMES=${VK_ICD_FILENAMES:-/usr/share/vulkan/icd.d/lvp_icd.json}
XVFB_PID=
if [ -z "${WIZ3D_TEST_DISPLAY:-}" ]; then
    Xvfb :99 -noreset -screen 0 3400x1200x24 >"$D/xvfb.log" 2>&1 &
    XVFB_PID=$!
fi
cleanup() { wineserver -k || true; [ -z "$XVFB_PID" ] || kill "$XVFB_PID" 2>/dev/null || true; }
trap cleanup EXIT
sleep 1
if [ "$LAUNCHER" = 1 ] && [ -z "${WIZ3D_TEST_DISPLAY:-}" ]; then
    # Emulate only KWin's advertised declaration contract in this private Xvfb.
    xprop -root -f _KDE_NET_WM_STEREO_CONTENT_SUPPORTED 32c -set _KDE_NET_WM_STEREO_CONTENT_SUPPORTED "${WIZ3D_TEST_SUPPORT:-2}"
fi
WINEDLLOVERRIDES=mscoree,mshtml= wineboot -u >"$D/wineboot.log" 2>&1
wineserver -w
cp /opt/dxvk/x64/d3d9.dll "$WINEPREFIX/drive_c/windows/system32/d3d9.dll"
# A 32-bit game runs in the WoW64 prefix, with its own DXVK in syswow64.
if [ "${WIZ3D_TEST_ARCH:-x64}" = x86 ]; then
    cp /opt/dxvk/x32/d3d9.dll "$WINEPREFIX/drive_c/windows/syswow64/d3d9.dll"
fi
export WINEDLLOVERRIDES='d3d9=n;d3dx9_43=b'
# The folder the proxy chain goes in: the game's, or with WIZ3D_TEST_PREFIX_INSTALL=1 the prefix's system folder, where
# DXVK's d3d9.dll moves to d3d9_real.dll and the proxy takes its name; wiz3D's logs then go to $D/logs.
# With =2 the launcher (WIZ3D_TEST_RUN, wiz3d-launch) does the installing and the removing, with the packaged configuration,
# and the prefix's system folders are compared before and after.
snapshot() { (cd "$WINEPREFIX/drive_c/windows" && find system32 syswow64 \( -type f -o -type l \) | LC_ALL=C sort | while read -r f; do
    if [ -L "$f" ]; then echo "L $f $(readlink "$f")"; else echo "F $f $(sha256sum < "$f")"; fi; done); }
TARGET=$D/game
LOGFILE=$D/game/wiz3D_proxy.log
mkdir -p "$TARGET/OutputMethods"
if [ "$PREFIX_INSTALL" = 1 ]; then
    SYS=$WINEPREFIX/drive_c/windows/system32
    [ "${WIZ3D_TEST_ARCH:-x64}" = x86 ] && SYS=$WINEPREFIX/drive_c/windows/syswow64
    mv "$SYS/d3d9.dll" "$SYS/d3d9_real.dll"
    mkdir -p "$SYS/OutputMethods" "$D/logs"
    rmdir "$D/game/OutputMethods"
    TARGET=$SYS
    LOGFILE=$D/logs/wiz3D_proxy.log
    export WIZ3D_LOG_DIR="Z:$(echo "$D/logs" | tr / '\\')"
fi
if [ "$PREFIX_INSTALL" = 2 ]; then
    mkdir -p "$D/logs"
    rmdir "$D/game/OutputMethods"
    LOGFILE=$D/logs/wiz3D_proxy.log
    export WIZ3D_LOG_DIR="Z:$(echo "$D/logs" | tr / '\\')"
    snapshot > "$D/prefix-before.txt"
fi
if [ "$MODE" != mono ] && [ "$PREFIX_INSTALL" != 2 ]; then
    cp "$DLL_DIR/"*.dll "$TARGET/"
    cp "$DLL_DIR/OutputMethods/SideBySideOutput.dll" "$TARGET/OutputMethods/"
    python3 - "$DLL_DIR/wiz3D_Config.xml" "$TARGET/wiz3D_Config.xml" "$SEPARATION" "$MODE" <<'PY'
import os
import sys
import xml.etree.ElementTree as E
E.register_namespace('', 'http://schemas.iz3d.com/config/2007')
tree = E.parse(sys.argv[1])
values = dict(OutputMethodDll='SideBySideOutput', OutputMode='3' if sys.argv[4] == 'full' else '0', OutputSpanMode='0',
              ShowFPS='0', ShowOSD='0', EnableAA='0', StereoBase=sys.argv[3], SwapEyes=os.environ.get('WIZ3D_TEST_SWAP', '0'),
              One_div_ZPS='0.5', AutoFocusEnable='0')
for node in tree.iter():
    tag = node.tag.split('}')[-1]
    if tag in values and (tag != 'SwapEyes' or 'Value' in node.attrib):
        node.set('Value', values[tag])
tree.write(sys.argv[2], encoding='utf-8', xml_declaration=True)
PY
    if [ "${WIZ3D_TEST_STAGED_CONFIG:-0}" = 1 ]; then
        cp "$DLL_DIR/wiz3D_Config.xml" "$TARGET/wiz3D_Config.xml"
    fi
fi
if [ "${WIZ3D_TEST_ARCH:-x64}" = x86 ]; then CC=i686-w64-mingw32-gcc; else CC=x86_64-w64-mingw32-gcc; fi
"$CC" -Wall -Wextra -O2 "$REPO/tools/run-wine/probe/probe.c" -o "$D/game/wiz3dprobe.exe" -ld3d9
cd "$D/game"
COMMAND=(wine wiz3dprobe.exe)
if [ "$LAUNCHER" != 0 ]; then
    COMMAND=("$LAUNCHER_BIN" --enable-3d -- "${COMMAND[@]}")
    if [ "$LAUNCHER" = 2 ]; then COMMAND[1]=--disable-3d; fi
fi
timeout 90 "${COMMAND[@]}" >"$D/probe.log" 2>&1 &
PROBE_PID=$!
for i in $(seq 1 60); do
    if grep -q 'PROBE: ready' "$D/probe.log"; then break; fi
    kill -0 "$PROBE_PID" || { tail -30 "$D/probe.log"; exit 1; }
    sleep 1
done
grep -q 'PROBE: ready' "$D/probe.log"
xwininfo -root -tree > "$D/tree.txt"
WID=$(awk '/wiz3dprobe-x/ {print $1; exit}' "$D/tree.txt")
if [ "$LAUNCHER" = 1 ]; then
    xprop -id "$WID" _NET_WM_PID WM_CLASS > "$D/identity.txt"
    python3 -c 'from pathlib import Path; print([(p.name, (p / "comm").read_text().strip()) for p in Path("/proc").iterdir() if p.name.isdigit()])' > "$D/processes.txt"
    find /tmp -maxdepth 2 -name window-state -exec cat {} \; > "$D/state.txt"
    for i in $(seq 1 30); do
        xprop -id "$WID" _KDE_NET_WM_STEREO_CONTENT _KDE_NET_WM_STEREO_CONTENT_CLASS > "$D/declaration.txt"
        if grep -q 'CLASS(CARDINAL) = 3, 3' "$D/declaration.txt"; then break; fi
        sleep .1
    done
    grep -q '^_KDE_NET_WM_STEREO_CONTENT(CARDINAL) = 3$' "$D/declaration.txt"
    grep -q '^_KDE_NET_WM_STEREO_CONTENT_CLASS(CARDINAL) = 3, 3$' "$D/declaration.txt"
fi
xprop -id "$WID" > "$D/xprop.txt"
xprop -id "$WID" WIZ3D_TEST > "$D/mirroring.txt"
xwd -id "$WID" -silent -out "$D/frame.xwd"
touch stop.flag
wait "$PROBE_PID"
! grep -q 'PROBE FAIL' "$D/probe.log"
grep -q 'PROBE: Win32 test property verified' "$D/probe.log"
grep -q 'no such atom' "$D/mirroring.txt"
grep -q 'DXVK: v2.7.1' "$D/probe.log"
grep -q 'llvmpipe' "$D/probe.log"
if [ "$MODE" != mono ]; then
    grep -q 'Routing through WRAPPER' "$LOGFILE"
    grep -q 'SideBySideOutput.dll.*native' "$D/probe.log"
fi
if [ "$PREFIX_INSTALL" = 2 ]; then
    snapshot > "$D/prefix-after.txt"
    cmp "$D/prefix-before.txt" "$D/prefix-after.txt"
    echo "PASS: the prefix's system folders are byte for byte as they were after the launcher took wiz3D out"
fi
if [ "$PREFIX_INSTALL" != 0 ] && [ "$MODE" != mono ]; then
    # The real Direct3D 9 is the one under its new name, and nothing of wiz3D's was written into the game folder or the prefix.
    grep -q 'Loaded .*d3d9_real.dll' "$D/probe.log"
    [ -s "$D/logs/wiz3D_proxy.log" ] && [ -d "$D/logs/Logs" ]
    ! find "$D/game" "$WINEPREFIX/drive_c/windows" \( -name wiz3D_proxy.log -o -name Statistic.xml -o -name Logs \) | grep .
    ! ls -A "$D/game" | grep -v -x -e wiz3dprobe.exe -e stop.flag | grep .
    echo "PASS: wiz3D installed in the prefix as d3d9.dll beside d3d9_real.dll; the game folder and the prefix hold none of its logs"
fi
if [ "$LAUNCHER" = 2 ]; then
    ! grep -q "^_KDE_NET_WM_STEREO_CONTENT(CARDINAL)" "$D/xprop.txt"
    MODE=mono
fi
python3 "$REPO/tools/run-wine/check.py" "$D/frame.xwd" "$D/frame.png" --mode "$MODE" --separation "$SEPARATION" --render-width "${PROBE_WIDTH:-800}" --render-height "${PROBE_HEIGHT:-600}" ${WIZ3D_TEST_SWAP:+--swapped} | tee "$D/measurements.txt"
