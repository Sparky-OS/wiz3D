#!/bin/sh
# Fetch the pinned xwin and let it splat the Windows SDK, CRT and ATL for
# x86 and x86_64 into debian/xwin. Writes debian/fetched.txt, the record of
# every download. None of it is installed in the package.
set -e
: "${XWIN_VERSION:?}" "${XWIN_SHA256:?}"
D=debian
URL=https://github.com/Jake-Shadle/xwin/releases/download/$XWIN_VERSION/xwin-$XWIN_VERSION-x86_64-unknown-linux-musl.tar.gz
mkdir -p $D/xwin-bin
curl -fsSL -o $D/xwin-bin/xwin.tar.gz "$URL"
echo "$XWIN_SHA256  $D/xwin-bin/xwin.tar.gz" | sha256sum -c -
tar -xz --strip-components=1 -C $D/xwin-bin -f $D/xwin-bin/xwin.tar.gz
$D/xwin-bin/xwin --version
mkdir -p $D/xwin-cache
$D/xwin-bin/xwin --accept-license --cache-dir $D/xwin-cache --arch x86,x86_64 --include-atl splat --output $D/xwin
{
    echo "Downloaded at build time, used to compile and link, not shipped:"
    echo "xwin $XWIN_VERSION: $URL (sha256 $XWIN_SHA256)"
    echo "xwin then reads Microsoft's Visual Studio 17 release channel manifest and downloads from download.visualstudio.microsoft.com:"
    python3 - $D/xwin-cache/dl <<'PY'
import glob, hashlib, json, os, sys
dl = sys.argv[1]
channel = json.load(open(os.path.join(dl, 'manifest_17.json')))['info']
print('  channel', channel['id'], 'build', channel['buildVersion'])
files = sorted(f for f in os.listdir(dl) if os.path.isfile(os.path.join(dl, f)))
for name in files:
    data = open(os.path.join(dl, name), 'rb').read()
    print('  %s %d %s' % (hashlib.sha256(data).hexdigest(), len(data), name))
vsman = json.load(open(glob.glob(os.path.join(dl, 'pkg_manifest_*.vsman'))[0]))
def walk(o):
    if isinstance(o, dict):
        if 'url' in o and os.path.basename(o.get('fileName', '').replace('\\', '/')) in files:
            yield o['url']
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)
print('  vsix payload URLs:')
for url in sorted(set(walk(vsman))):
    print('   ', url)
PY
} > $D/fetched.txt
