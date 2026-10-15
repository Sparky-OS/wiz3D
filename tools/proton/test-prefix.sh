#!/bin/bash
# With Wine, DXVK and the package installed, as an ordinary user: wiz3d-launch makes a prefix that does not exist
# (win64 by default, win32 with WINEARCH), with DXVK, the user folders inside it, Z: present and no menu entries.
# Usage: test-prefix.sh NEW-EVIDENCE-DIRECTORY
set -u
D=$(realpath -m "${1:?Usage: test-prefix.sh NEW-EVIDENCE-DIRECTORY}")
[ ! -e "$D" ] || { echo "Refusing to reuse $D" >&2; exit 2; }
mkdir -p "$D"
LAUNCH=${WIZ3D_TEST_LAUNCH:-/usr/bin/wiz3d-launch}
export HOME=$D/home
mkdir -p "$HOME/Documents" "$HOME/.local/share/applications"
echo "real" > "$HOME/Documents/marker.txt"
status=0
fail() { echo "FAIL: $*"; status=1; }
check_prefix() {  # check_prefix PREFIX ARCH
    local P=$1 arch=$2 user
    grep -q "^#arch=$arch" "$P/system.reg" || fail "$arch: system.reg says $(grep '^#arch' "$P/system.reg")"
    user=$(ls "$P/drive_c/users" | grep -v Public | head -1)
    if [ "$arch" = win64 ]; then
        [ "$(readlink "$P/drive_c/windows/system32/d3d9.dll")" = /usr/lib/dxvk/wine64/d3d9.dll.so ] || fail "$arch: system32 d3d9.dll is $(readlink "$P/drive_c/windows/system32/d3d9.dll")"
        [ "$(readlink "$P/drive_c/windows/syswow64/d3d9.dll")" = /usr/lib/dxvk/wine32/d3d9.dll.so ] || fail "$arch: syswow64 d3d9.dll is $(readlink "$P/drive_c/windows/syswow64/d3d9.dll")"
    else
        [ "$(readlink "$P/drive_c/windows/system32/d3d9.dll")" = /usr/lib/dxvk/wine32/d3d9.dll.so ] || fail "$arch: system32 d3d9.dll is $(readlink "$P/drive_c/windows/system32/d3d9.dll")"
        [ ! -e "$P/drive_c/windows/syswow64" ] || fail "$arch: a syswow64 exists"
    fi
    for f in Documents Desktop Downloads; do
        [ -d "$P/drive_c/users/$user/$f" ] && [ ! -L "$P/drive_c/users/$user/$f" ] || fail "$arch: $f is not a folder of the prefix ($(readlink "$P/drive_c/users/$user/$f"))"
    done
    [ ! -e "$P/drive_c/users/$user/Documents/marker.txt" ] || fail "$arch: Documents reaches the real home"
    [ "$(readlink "$P/dosdevices/z:")" = / ] || fail "$arch: Z: is $(readlink "$P/dosdevices/z:")"
    grep -q '"winemenubuilder.exe"=""' "$P/user.reg" || fail "$arch: winemenubuilder is not turned off"
    [ -z "$(ls "$HOME/.local/share/applications")" ] || fail "$arch: menu entries were written: $(ls "$HOME/.local/share/applications")"
}
export WINEDEBUG=-all
P=$D/p64
WINEPREFIX=$P "$LAUNCH" --disable-3d -- wine cmd /c ver > "$D/make-win64.log" 2>&1 || fail "win64: wiz3d-launch exit $?"
WINEPREFIX=$P wineserver -w
grep -q 'making the win64 prefix' "$D/make-win64.log" || fail "win64: not announced"
check_prefix "$P" win64
WINEPREFIX=$P "$LAUNCH" --disable-3d -- wine cmd /c ver > "$D/again-win64.log" 2>&1 || fail "win64 again: exit $?"
WINEPREFIX=$P wineserver -w
grep -q 'making the' "$D/again-win64.log" && fail "win64: made twice"
[ $status = 0 ] && echo "PASS: a missing WINEPREFIX becomes a win64 prefix with DXVK in both system folders, its own user folders, Z:, no menu entries; the second run leaves it alone"
P=$D/p32
WINEPREFIX=$P WINEARCH=win32 "$LAUNCH" --disable-3d -- wine cmd /c ver > "$D/make-win32.log" 2>&1 || fail "win32: wiz3d-launch exit $?"
WINEPREFIX=$P wineserver -w
check_prefix "$P" win32
[ $status = 0 ] && echo "PASS: WINEARCH=win32 makes a 32-bit prefix with DXVK's 32-bit DLLs in system32"
P=$D/p99
out=$(WINEPREFIX=$P WINEARCH=win99 "$LAUNCH" --disable-3d -- wine cmd /c ver 2>&1); rc=$?
[ $rc != 0 ] && echo "$out" | grep -q 'WINEARCH must be' && [ ! -e "$P" ] && echo "PASS: a wrong WINEARCH is refused before anything is made" || fail "WINEARCH=win99: rc=$rc $out"
rm -rf "$D/p64" "$D/p32" "$HOME/.cache/wine"  # the prefixes are large; the logs stay
exit $status
