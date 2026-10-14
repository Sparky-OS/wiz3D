# SPDX-License-Identifier: LGPL-2.1-or-later
"""Place wiz3D's Direct3D 9 proxy in a Wine prefix in front of DXVK, and take it out again.

Everything it makes is a symbolic link into /usr/lib/wiz3d, so `off` removes exactly what `on` made and
puts DXVK's d3d9.dll back where it was.  Both are idempotent.  The real Direct3D 9 is reached as
d3d9_real.dll in the same folder: the proxy and the wrapper look for that name first."""
import os
import sys

WIZ3D = os.environ.get('WIZ3D_DIR', '/usr/lib/wiz3d')
FILES = ('d3d9.dll', 'S3DWrapperD3D9.dll', 'S3DAPI.dll', 'ZLOg.dll', 'wiz3D_Config.xml', 'BaseProfile.xml', 'OutputMethods')


def system_dirs(prefix):
    windows = os.path.join(prefix, 'drive_c', 'windows')
    dirs = [(os.path.join(windows, 'system32'), 'x64')]
    if os.path.isdir(os.path.join(windows, 'syswow64')):
        dirs.append((os.path.join(windows, 'syswow64'), 'x86'))
    return dirs


def ours(path):
    return os.path.islink(path) and os.readlink(path).startswith(WIZ3D + '/')


def is_dxvk(path):
    try:
        with open(path, 'rb') as dll:
            return b'DXVK_' in dll.read()
    except OSError:
        return False


def on(prefix):
    """Put wiz3D in the prefix's system folders that hold DXVK's Direct3D 9; returns the folders without it.

    RuntimeError says why it cannot, before anything is changed, when no folder holds DXVK's."""
    candidates = [(folder, arch) for folder, arch in system_dirs(prefix) if os.path.isdir(os.path.join(WIZ3D, arch))]
    if not candidates:
        raise RuntimeError('wiz3D has no files for this prefix (%s)' % WIZ3D)
    folders = [(folder, arch) for folder, arch in candidates if ours(os.path.join(folder, 'd3d9.dll')) or is_dxvk(os.path.join(folder, 'd3d9.dll'))]
    if not folders:
        raise RuntimeError('wiz3D needs DXVK for Direct3D 9, and %s is not DXVK\'s: turn DXVK on for this game' % os.path.join(candidates[0][0], 'd3d9.dll'))
    for folder, arch in folders:
        d3d9, real = os.path.join(folder, 'd3d9.dll'), os.path.join(folder, 'd3d9_real.dll')
        if not ours(d3d9):
            if os.path.lexists(real):
                os.remove(real)
            os.rename(d3d9, real)
        for name in FILES:
            target = os.path.join(folder, name)
            if os.path.lexists(target):
                os.remove(target)
            os.symlink(os.path.join(WIZ3D, arch, name), target)
    return [folder for folder, arch in candidates if (folder, arch) not in folders]


def off(prefix):
    """Take wiz3D out and put DXVK's d3d9.dll back; harmless when wiz3D is not in the prefix."""
    for folder, arch in system_dirs(prefix):
        real = os.path.join(folder, 'd3d9_real.dll')
        for name in FILES:
            target = os.path.join(folder, name)
            if ours(target):
                os.remove(target)
        if os.path.lexists(real):
            if not os.path.lexists(os.path.join(folder, 'd3d9.dll')):
                os.rename(real, os.path.join(folder, 'd3d9.dll'))  # the file moved aside by `on`
            elif os.path.islink(real):
                os.remove(real)  # DXVK put its own link back since: ours is stale


if __name__ == '__main__':
    {'on': on, 'off': off}[sys.argv[1]](sys.argv[2])
