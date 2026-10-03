#!/bin/bash
# Run inside wiz3d-wine-test. Output must be a new directory in the workspace.
set -euo pipefail
REPO=$(realpath "$1")
D=$(realpath -m "$2")
MODE=${3:-half}
SEPARATION=${4:-0.16}
[ ! -e "$D" ] || { echo "Refusing to reuse evidence directory: $D" >&2; exit 2; }
mkdir -p "$D/game/OutputMethods"
export WINEPREFIX=$D/prefix WINEARCH=win64 WINEDEBUG=+loaddll
export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=4
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
Xvfb :99 -screen 0 1800x900x24 >"$D/xvfb.log" 2>&1 &
XVFB_PID=$!
cleanup() { wineserver -k || true; kill "$XVFB_PID" 2>/dev/null || true; }
trap cleanup EXIT
sleep 1
wineboot -u >"$D/wineboot.log" 2>&1
wineserver -w
cp /opt/dxvk/x64/d3d9.dll "$WINEPREFIX/drive_c/windows/system32/d3d9.dll"
export WINEDLLOVERRIDES='d3d9=n;d3dx9_43=b'
if [ "$MODE" != mono ]; then
    cp "$REPO/out/x64/"*.dll "$D/game/"
    cp "$REPO/out/x64/OutputMethods/SideBySideOutput.dll" "$D/game/OutputMethods/"
    python3 - "$REPO/out/x64/wiz3D_Config.xml" "$D/game/wiz3D_Config.xml" "$SEPARATION" <<'PY'
import sys
import xml.etree.ElementTree as E
E.register_namespace('', 'http://schemas.iz3d.com/config/2007')
tree = E.parse(sys.argv[1])
values = dict(OutputMethodDll='SideBySideOutput', OutputMode='0', OutputSpanMode='0',
              ShowFPS='0', ShowOSD='0', EnableAA='0', StereoBase=sys.argv[3],
              One_div_ZPS='0.5', AutoFocusEnable='0')
for node in tree.iter():
    tag = node.tag.split('}')[-1]
    if tag in values:
        node.set('Value', values[tag])
tree.write(sys.argv[2], encoding='utf-8', xml_declaration=True)
PY
fi
x86_64-w64-mingw32-gcc -Wall -Wextra -O2 "$REPO/tools/run-wine/probe/probe.c" -o "$D/game/wiz3dprobe.exe" -ld3d9
cd "$D/game"
timeout 90 wine wiz3dprobe.exe >"$D/probe.log" 2>&1 &
PROBE_PID=$!
for i in $(seq 1 60); do
    if grep -q 'PROBE: ready' "$D/probe.log"; then break; fi
    kill -0 "$PROBE_PID" || { tail -30 "$D/probe.log"; exit 1; }
    sleep 1
done
grep -q 'PROBE: ready' "$D/probe.log"
xwininfo -root -tree > "$D/tree.txt"
WID=$(awk '/wiz3dprobe-x/ {print $1; exit}' "$D/tree.txt")
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
python3 "$REPO/tools/run-wine/check.py" "$D/frame.xwd" "$D/frame.png" --mode "$MODE" --separation "$SEPARATION" | tee "$D/measurements.txt"
