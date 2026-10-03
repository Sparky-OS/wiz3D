#!/bin/bash
# Host entry point. Builds and runs only in containers, without GPU/display mounts.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
WORKSPACE=$(dirname "$REPO")
OUT=${1:?Usage: modes-test.sh NEW-EVIDENCE-DIRECTORY}
mkdir -p "$OUT"
OUT=$(realpath "$OUT")
case "$OUT/" in "$WORKSPACE/"*) ;; *) echo 'Output must be in workspace' >&2; exit 2;; esac
for CASE in mono half half-low; do
    MODE=$CASE; SEPARATION=.16
    if [ "$CASE" = half-low ]; then MODE=half; SEPARATION=.08; fi
    CID=$(docker run -d --cpus 4 -v "$WORKSPACE:$WORKSPACE" wiz3d-wine-test \
        bash "$REPO/tools/run-wine/run-test.sh" "$REPO" "$OUT/$CASE" "$MODE" "$SEPARATION")
    trap 'docker rm -f "$CID" >/dev/null' EXIT
    RESULT=$(docker wait "$CID")
    docker logs "$CID" > "$OUT/$CASE.log" 2>&1
    cat "$OUT/$CASE.log"
    docker rm "$CID" >/dev/null
    trap - EXIT
    [ "$RESULT" = 0 ] || exit "$RESULT"
done
