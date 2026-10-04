#!/bin/sh
# Build the wiz3d package from the committed tree in a freshly updated
# debian:testing container. Needs Docker and network (xwin, Windows SDK).
# Usage: build-deb.sh OUTPUT-DIRECTORY (new; holds the .deb, .changes, .buildinfo)
set -e
SOL=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=$(realpath -m "${1:?Usage: build-deb.sh OUTPUT-DIRECTORY}")
[ ! -e "$OUT" ] || { echo "Refusing to reuse $OUT" >&2; exit 2; }
VERSION=$(sed -n '1s/^wiz3d (\(.*\)) .*/\1/p' "$SOL/debian/changelog")
mkdir -p "$OUT/home" "$OUT/src/wiz3d-$VERSION"
git -C "$SOL" archive HEAD | tar -x -C "$OUT/src/wiz3d-$VERSION"
if ! docker image inspect wiz3d-deb-build >/dev/null 2>&1; then
    DOCKER_BUILDKIT=0 docker build --pull --no-cache --cpu-quota=400000 -t wiz3d-deb-build - <<'DOCKERFILE'
FROM debian:testing
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get -y dist-upgrade \
 && apt-get -y install --no-install-recommends build-essential debhelper dpkg-dev fakeroot lintian \
    clang lld llvm llvm-tools ninja-build python3 ca-certificates curl xz-utils \
 && rm -rf /var/lib/apt/lists/*
DOCKERFILE
fi
CONTAINER=$(docker run -d --cpus 4 -u "$(id -u):$(id -g)" -e HOME="$OUT/home" -v "$OUT:$OUT" -w "$OUT/src/wiz3d-$VERSION" \
    wiz3d-deb-build sh -c 'dpkg-buildpackage -b -uc -us && lintian --info --display-info --tag-display-limit 0 ../*.changes > ../lintian.txt 2>&1; echo "lintian exit $?" >> ../lintian.txt')
trap 'docker rm -f "$CONTAINER" >/dev/null' EXIT HUP INT TERM
RESULT=$(docker wait "$CONTAINER")
docker logs "$CONTAINER"
exit "$RESULT"
