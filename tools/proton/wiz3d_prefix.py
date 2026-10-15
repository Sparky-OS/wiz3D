# SPDX-License-Identifier: LGPL-2.1-or-later
"""Place wiz3D's Direct3D 9 proxy in a Wine prefix in front of DXVK, and take it out again.

Everything it makes is a symbolic link into /usr/lib/wiz3d, so `off` removes exactly what `on` made and
puts DXVK's d3d9.dll back where it was.  Both are idempotent.  The real Direct3D 9 is reached as
d3d9_real.dll in the same folder: the proxy and the wrapper look for that name first."""
import os
import stat
import string
import sys

WIZ3D = os.environ.get('WIZ3D_DIR', '/usr/lib/wiz3d')
FILES = ('d3d9.dll', 'S3DWrapperD3D9.dll', 'S3DAPI.dll', 'ZLOg.dll', 'wiz3D_Config.xml', 'BaseProfile.xml', 'OutputMethods')


def arch(prefix):
    """'win32' or 'win64', as the prefix's system.reg says; a prefix without one is judged by its folders."""
    try:
        with open(os.path.join(prefix, 'system.reg'), encoding='utf-8', errors='replace') as reg:
            for line in reg:
                if line.startswith('#arch='):
                    return line[6:].strip()
                if not line.startswith(('WINE REGISTRY', '#', ';')):
                    break
    except OSError:
        pass
    return 'win64' if os.path.isdir(os.path.join(prefix, 'drive_c', 'windows', 'syswow64')) else 'win32'


def system_dirs(prefix):
    """The prefix's system folders with the wiz3D tree each one takes: x86 in a 32-bit prefix's system32."""
    windows = os.path.join(prefix, 'drive_c', 'windows')
    if arch(prefix) == 'win32':
        return [(os.path.join(windows, 'system32'), 'x86')]
    dirs = [(os.path.join(windows, 'system32'), 'x64')]
    if os.path.isdir(os.path.join(windows, 'syswow64')):
        dirs.append((os.path.join(windows, 'syswow64'), 'x86'))
    return dirs


def default_prefix():
    """The prefix the game will run in: WINEPREFIX, Proton's, or Wine's own default."""
    if os.environ.get('WINEPREFIX'):
        return os.environ['WINEPREFIX']
    if os.environ.get('STEAM_COMPAT_DATA_PATH'):
        return os.path.join(os.environ['STEAM_COMPAT_DATA_PATH'], 'pfx')
    return os.path.expanduser('~/.wine')


def windows_path(path, prefix=None):
    """A Unix path the way Wine names it to Windows code: through the drive of the prefix that holds it
    (the lowest letter, from the longest folder, as Wine's own lookup does), or as \\\\?\\unix\\... when no
    drive does, which Wine accepts everywhere a path is taken.  So nothing here needs the Z: drive."""
    path = os.path.abspath(path)
    prefix = prefix or default_prefix()
    drives = {}
    for letter in string.ascii_lowercase:
        try:
            info = os.stat(os.path.join(prefix, 'dosdevices', letter + ':'))
        except OSError:
            continue
        drives.setdefault((info.st_dev, info.st_ino), letter)
    folder = path
    while True:
        try:
            info = os.stat(folder)
            if stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) in drives:
                rest = path[len(folder):].lstrip('/')
                return drives[(info.st_dev, info.st_ino)].upper() + ':\\' + rest.replace('/', '\\')
        except OSError:
            pass
        if folder == '/':
            break
        folder = os.path.dirname(folder)
    return '\\\\?\\unix' + path.replace('/', '\\')


USER_FOLDERS = ('Desktop', 'Documents', 'Downloads', 'Music', 'Pictures', 'Videos', 'Templates')


def create(prefix, arch=None, log=None):
    """Make a prefix for a game, the way a game manager does: wineboot for the architecture (WINEARCH, else
    win64), the system's DXVK through dxvk-setup, the user folders as plain folders inside the prefix instead
    of links to the real home (a game then reads and writes its settings there, never in ~/Documents), and
    no menu entries or file associations from the games it will run.  Z: stays.  Nothing is downloaded."""
    import shutil
    import subprocess
    arch = arch or os.environ.get('WINEARCH') or 'win64'
    if arch not in ('win32', 'win64'):
        raise RuntimeError('WINEARCH must be win32 or win64, not %r' % arch)
    loader = shutil.which('wine32' if arch == 'win32' else 'wine64') or shutil.which('wine')
    setup = shutil.which('dxvk-setup')
    if not loader or not setup:
        raise RuntimeError('the prefix %s does not exist and %s is not installed to make it' % (prefix, 'wine' if not loader else 'dxvk-setup'))
    env = dict(os.environ, WINEPREFIX=prefix, WINEARCH=arch, WINE=loader, WINEDEBUG=os.environ.get('WINEDEBUG', '-all'),
               WINEDLLOVERRIDES='mscoree,mshtml,winemenubuilder.exe=')
    say = log or (lambda text: print('wiz3d-launch: ' + text, file=sys.stderr))
    say('making the %s prefix %s with DXVK, its own user folders and no menu entries' % (arch, prefix))

    def run(command):
        done = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if done.returncode:
            raise RuntimeError('%s failed (%d):\n%s' % (os.path.basename(command[0]), done.returncode, '\n'.join(done.stdout.splitlines()[-12:])))

    run([loader, 'wineboot', '-u'])
    run([loader, 'reg', 'add', r'HKEY_CURRENT_USER\Software\Wine\DllOverrides', '/v', 'winemenubuilder.exe', '/d', '', '/f'])
    run([setup, 'install'])
    # Microsoft's d3dx9 and shader compiler, as Lutris's D3D Extras: Wine's own compiler refuses the HLSL of
    # older games (TrackMania Nations Forever: "Unexpected modifier used on a function").  Through winetricks,
    # which fetches them from Microsoft and keeps them in its cache; WIZ3D_WINETRICKS=0 leaves them out.
    winetricks = shutil.which('winetricks')
    if winetricks and os.environ.get('WIZ3D_WINETRICKS', '1') != '0':
        say('adding d3dx9 and d3dcompiler_43 with winetricks')
        run([winetricks, '-q', 'd3dx9', 'd3dcompiler_43'])
    elif not winetricks:
        say('winetricks is not installed: games that need Microsoft\'s d3dx9 or shader compiler will miss them')
    if shutil.which('wineserver'):
        subprocess.run(['wineserver', '-w'], env=env)
    isolate(prefix)


def game_folder(command):
    """The folder of the first Windows program the command names by a Unix path, or None."""
    for word in command:
        if word.lower().endswith('.exe') and os.path.dirname(word) and os.path.isdir(os.path.dirname(word)):
            return os.path.dirname(os.path.abspath(word))
    return None


def isolate(prefix):
    """Replace the links from the prefix's user folders to the real home with folders of the prefix."""
    users = os.path.join(prefix, 'drive_c', 'users')
    for user in os.listdir(users) if os.path.isdir(users) else ():
        if user == 'Public':
            continue
        for name in USER_FOLDERS:
            folder = os.path.join(users, user, name)
            if os.path.islink(folder):
                os.remove(folder)
                os.mkdir(folder)


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
