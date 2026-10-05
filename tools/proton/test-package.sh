#!/bin/bash
# Host entry point: install the built wiz3d package in a throwaway container
# from the base image (fresh debian:testing + the dev repository + Wine), run
# the suites as an ordinary user, remove the package, check no game file moved.
# The base image is made by pkg/setup-base.sh equivalents: see REPORT.md.
# Usage: test-package.sh DEB-DIRECTORY NEW-EVIDENCE-DIRECTORY [SUITE...]
#   suites: kwin frames (default); kwin-dxvk, kwin-gl on request (WIZ3D_TEST_WINE: patched Wine install,
#   WIZ3D_TEST_CAPTURE: folder with KWin's kwin-capture helper)
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
DEBS=$(realpath "${1:?Usage: test-package.sh DEB-DIRECTORY NEW-EVIDENCE-DIRECTORY [SUITE...]}")
OUT=$(realpath -m "${2:?}")
shift 2
SUITES=${*:-kwin frames}
[ ! -e "$OUT" ] || { echo "Refusing to reuse $OUT" >&2; exit 2; }
mkdir -p "$OUT"
CID=$(docker run -d --cpus 4 --cap-add SYS_NICE --device /dev/dri/renderD128 --group-add 125 \
    -v /K3D/temp/sparky-os/repo:/repo:ro -v "$DEBS:/deb:ro" -v "$REPO:$REPO:ro" -v "$OUT:$OUT" \
    -e REPO="$REPO" -e OUT="$OUT" -e SUITES="$SUITES" -e TESTUID="$(id -u)" -e WIZ3D_TEST_ARCH="${WIZ3D_TEST_ARCH:-x64}" -e WIZ3D_TEST_SUPPORT="${WIZ3D_TEST_SUPPORT:-2}" ${WIZ3D_TEST_WINE:+-v "$WIZ3D_TEST_WINE:/opt/wine-stereo:ro" -e WIZ3D_TEST_WINE=1} ${WIZ3D_TEST_CAPTURE:+-v "$WIZ3D_TEST_CAPTURE:/opt/wiz3d-capture:ro"} wiz3d-pkgtest-base bash -c '
set -u
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get -y install /deb/wiz3d_*.deb > "$OUT/install.log" 2>&1 || { tail -20 "$OUT/install.log"; exit 1; }
dpkg -l wiz3d kwin-wayland libstereo-declare1 mesa-vulkan-drivers wine64 | grep ^ii | tee "$OUT/versions.txt"
dpkg -L wiz3d > "$OUT/installed-files.txt"
groupadd -g 125 hostrender
usermod -aG hostrender tester
# A game folder that is not opted in, and one that is: neither may change when the package goes.
mkdir -p /home/tester/games/other /home/tester/games/opted-in
echo original-d3d9 > /home/tester/games/other/d3d9.dll
echo game-data > /home/tester/games/other/game.dat
cp -r /usr/lib/wiz3d/x64/. /home/tester/games/opted-in/
echo game-exe > /home/tester/games/opted-in/game.exe
chown -R tester /home/tester/games
( cd /home/tester/games && find . -type f | sort | xargs sha256sum ) > "$OUT/games-before.sha256"
cd "$REPO"
status=0
for suite in $SUITES; do
    case $suite in
        kwin) script=test-kwin.sh;;
        frames) script=test-installed.sh;;
        kwin-dxvk) script=test-kwin-dxvk.sh;;
        kwin-gl) script=test-kwin-gl.sh;;
    esac
    runuser -u tester -- env HOME=/home/tester WIZ3D_TEST_ARCH="$WIZ3D_TEST_ARCH" WIZ3D_TEST_SUPPORT="$WIZ3D_TEST_SUPPORT" ${WIZ3D_TEST_WINE:+PATH=/opt/wine-stereo/bin:$PATH} "$REPO/tools/proton/$script" "$OUT/$suite" > "$OUT/$suite.log" 2>&1 || { echo "FAIL: suite $suite"; status=1; }
    tail -20 "$OUT/$suite.log"
done
( cd /home/tester/games && find . -type f | sort | xargs sha256sum ) > "$OUT/games-after-tests.sha256"
apt-get -y remove wiz3d > "$OUT/remove.log" 2>&1
{
  echo "after remove:"; ls -d /usr/lib/wiz3d /usr/bin/wiz3d-run /usr/share/doc/wiz3d 2>&1
  dpkg -l wiz3d | tail -1
} > "$OUT/after-remove.txt"
cat "$OUT/after-remove.txt"
( cd /home/tester/games && find . -type f | sort | xargs sha256sum ) > "$OUT/games-after-remove.sha256"
cmp "$OUT/games-before.sha256" "$OUT/games-after-remove.sha256" && echo "PASS: no game file changed by install, tests or removal"
! test -e /usr/lib/wiz3d && ! test -e /usr/bin/wiz3d-run && echo "PASS: package files gone after removal"
chown -R '"$(id -u)"' "$OUT" 2>/dev/null
exit $status
')
RC=$(docker wait "$CID")
docker logs "$CID" > "$OUT/container.log" 2>&1
cat "$OUT/container.log"
docker rm "$CID" >/dev/null
exit "$RC"
