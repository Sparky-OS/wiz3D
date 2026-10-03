#!/bin/bash
# Run the full-SBS suite in containers. The shared helper is built separately.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
WORKSPACE=$(dirname "$REPO")
OUT=$(realpath -m "${1:?Usage: test.sh NEW-EVIDENCE-DIRECTORY HELPER-INSTALL-PREFIX}")
HELPER=$(realpath "${2:?Supply the installed shared stereo-declare prefix}")
for PATH_TO_CHECK in "$OUT" "$HELPER"; do
    case "$PATH_TO_CHECK/" in "$WORKSPACE/"*) ;; *) echo 'Paths must be within workspace' >&2; exit 2;; esac
done
[ ! -e "$OUT" ] || { echo 'Evidence directory already exists' >&2; exit 2; }
mkdir -p "$OUT"
for CASE in normal low high reset reset-width disabled fullscreen; do
    ENV=(-e WIZ3D_TEST_LAUNCHER=1 -e LD_LIBRARY_PATH="$HELPER/lib")
    case $CASE in
        low) ENV+=(-e PROBE_WIDTH=400 -e PROBE_HEIGHT=300);;
        high) ENV+=(-e PROBE_WIDTH=1200 -e PROBE_HEIGHT=900);;
        reset) ENV+=(-e PROBE_RESET=1 -e PROBE_RESET_AUTO=1);;
        reset-width) ENV+=(-e PROBE_RESET=1 -e PROBE_RESET_WIDTH_ONLY=1);;
        disabled) ENV=(-e WIZ3D_TEST_LAUNCHER=2 -e LD_LIBRARY_PATH="$HELPER/lib");;
        fullscreen) ENV+=(-e PROBE_FULLSCREEN=1);;
    esac
    CID=$(docker run -d --cpus 4 -e WIZ3D_TEST_DLL_DIR="${WIZ3D_TEST_DLL_DIR:-$REPO/out/x64}" "${ENV[@]}" -v "$WORKSPACE:$WORKSPACE" wiz3d-proton-test \
        bash "$REPO/tools/run-wine/run-test.sh" "$REPO" "$OUT/$CASE" full .16)
    trap 'docker rm -f "$CID" >/dev/null' EXIT
    RESULT=$(docker wait "$CID")
    docker logs "$CID" > "$OUT/$CASE.log" 2>&1
    cat "$OUT/$CASE.log"
    docker rm "$CID" >/dev/null
    trap - EXIT
    [ "$RESULT" = 0 ] || exit "$RESULT"
done
CID=$(docker run -d --cpus 4 -e WIZ3D_TEST_DLL_DIR="${WIZ3D_TEST_DLL_DIR:-$REPO/out/x64}" -e LD_LIBRARY_PATH="$HELPER/lib" -v "$WORKSPACE:$WORKSPACE" wiz3d-proton-test \
    sh -c 'Xvfb :99 -noreset -screen 0 1800x900x24 & sleep 1; DISPLAY=:99 timeout 30 python3 -u "$1/tools/proton/test-launcher.py"' sh "$REPO")
trap 'docker rm -f "$CID" >/dev/null' EXIT
RESULT=$(docker wait "$CID")
docker logs "$CID" > "$OUT/launcher.log" 2>&1
cat "$OUT/launcher.log"
docker rm "$CID" >/dev/null
trap - EXIT
[ "$RESULT" = 0 ] || exit "$RESULT"
