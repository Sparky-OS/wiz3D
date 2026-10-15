#!/usr/bin/env python3
"""Write a clang VFS overlay that makes include lookup case-insensitive.

The code was written for MSVC on Windows and spells #include names and
directories with a different case from the files on disk ("StdAfx.h" for
stdafx.h, "..\\streamer\\X.h" for Streamer/). Linux filesystems are case
sensitive. clang's overlay with case-sensitive=false resolves every path under
the listed roots case-insensitively, so no source change or symlink farm is
needed. Usage: make_vfs.py <out.json> <root>...
"""
import json, os, sys

SKIP = {'.git', 'build-linux-obj', 'out'}


def tree(path):
    ents, seen = [], set()
    for name in sorted(os.listdir(path)):
        low = name.lower()
        if low in seen or name in SKIP:
            continue
        seen.add(low)
        full = os.path.join(path, name)
        if os.path.isdir(full):
            if os.path.islink(full) and os.path.realpath(path).startswith(os.path.realpath(full)):
                continue  # a link back up the tree, as xwin makes include/<SDK version> -> .
            ents.append({'type': 'directory', 'name': name,
                         'contents': tree(full)})
        else:
            ents.append({'type': 'file', 'name': name,
                         'external-contents': os.path.realpath(full)})
    return ents


def main(out, roots):
    entries = [{'type': 'directory', 'name': os.path.abspath(r),
                'contents': tree(os.path.abspath(r))} for r in roots]
    with open(out, 'w') as f:
        json.dump({'version': 0, 'case-sensitive': 'false',
                   'use-external-names': 'false', 'roots': entries}, f)
    print(f'vfs overlay: {len(roots)} roots -> {out}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
