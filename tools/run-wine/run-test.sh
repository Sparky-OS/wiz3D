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
mkdir -p "$D/game/OutputMethods"
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
if [ "$MODE" != mono ]; then
    cp "$DLL_DIR/"*.dll "$D/game/"
    cp "$DLL_DIR/OutputMethods/SideBySideOutput.dll" "$D/game/OutputMethods/"
    python3 - "$DLL_DIR/wiz3D_Config.xml" "$D/game/wiz3D_Config.xml" "$SEPARATION" "$MODE" <<'PY'
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
        cp "$DLL_DIR/wiz3D_Config.xml" "$D/game/wiz3D_Config.xml"
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
    grep -q 'Routing through WRAPPER' wiz3D_proxy.log
    grep -q 'SideBySideOutput.dll.*native' "$D/probe.log"
fi
if [ "$LAUNCHER" = 2 ]; then
    ! grep -q "^_KDE_NET_WM_STEREO_CONTENT(CARDINAL)" "$D/xprop.txt"
    MODE=mono
fi
python3 "$REPO/tools/run-wine/check.py" "$D/frame.xwd" "$D/frame.png" --mode "$MODE" --separation "$SEPARATION" --render-width "${PROBE_WIDTH:-800}" --render-height "${PROBE_HEIGHT:-600}" ${WIZ3D_TEST_SWAP:+--swapped} | tee "$D/measurements.txt"
