#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""wiz3d-launch against a made-up prefix: what it places, what it refuses, and that the prefix comes back byte for byte."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

LAUNCH = Path(os.environ.get("WIZ3D_TEST_LAUNCH") or Path(__file__).with_name("wiz3d-launch"))


def tree(root):
    """Every file and link of a folder with its content hash or link target."""
    result = {}
    for path in sorted(Path(root).rglob('*')):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            result[rel] = 'L ' + os.readlink(path)
        elif path.is_file():
            result[rel] = 'F ' + hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            result[rel] = 'D'
    return result


def run(prefix, *args, **env):
    full = dict(os.environ, WINEPREFIX=str(prefix), WIZ3D_DIR=str(wiz3d), WIZ3D_RUN=str(stub), WIZ3D_LOG_DIR=str(logs))
    full.update(env)
    return subprocess.run([str(LAUNCH), *args], env=full, capture_output=True, text=True)


with tempfile.TemporaryDirectory() as temp:
    temp = Path(temp)
    wiz3d = temp / 'usr-lib-wiz3d'
    for arch in ('x64', 'x86'):
        (wiz3d / arch / 'OutputMethods').mkdir(parents=True)
        for name in ('d3d9.dll', 'S3DWrapperD3D9.dll', 'S3DAPI.dll', 'ZLOg.dll', 'wiz3D_Config.xml', 'BaseProfile.xml'):
            (wiz3d / arch / name).write_bytes(f'wiz3d {arch} {name}'.encode())
    logs = temp / 'logs'
    # The stand-in for wiz3d-run records what the prefix looked like while the game ran.
    stub = temp / 'wiz3d-run'
    stub.write_text('#!/bin/sh\nshift\nls -l "$WINEPREFIX/drive_c/windows/system32/d3d9.dll" "$WINEPREFIX/drive_c/windows/system32/d3d9_real.dll" '
                    '"$WINEPREFIX/drive_c/windows/syswow64/d3d9_real.dll" > "$WINEPREFIX/during.txt" 2>&1\n'
                    'printf "log dir: %s\\n" "$WIZ3D_LOG_DIR" >> "$WINEPREFIX/during.txt"\nprintf "cwd: %s\\n" "$PWD" >> "$WINEPREFIX/during.txt"\nexit 5\n')
    stub.chmod(0o755)

    def make_prefix(name, dxvk=True, arch='win64', drives=('z:',)):
        prefix = temp / name
        folders = (('system32', 'x64'), ('syswow64', 'x86')) if arch == 'win64' else (('system32', 'x86'),)
        for folder, tree_arch in folders:
            (prefix / 'drive_c' / 'windows' / folder).mkdir(parents=True)
            body = b'MZ DXVK_HUD d3d9 ' + tree_arch.encode() if dxvk else b'MZ Wine placeholder DLL'
            (prefix / 'drive_c' / 'windows' / folder / 'd3d9.dll').write_bytes(body)
            (prefix / 'drive_c' / 'windows' / folder / 'dxgi.dll').write_bytes(b'dxgi')
        (prefix / 'system.reg').write_text(f'WINE REGISTRY Version 2\n;; All keys relative to \\\\Machine\n\n#arch={arch}\n\n[Software\\\\Wine]\n')
        (prefix / 'dosdevices').mkdir()
        (prefix / 'dosdevices' / 'c:').symlink_to(prefix / 'drive_c')
        for drive in drives:
            (prefix / 'dosdevices' / drive).symlink_to('/')
        return prefix

    prefix = make_prefix('pfx')
    before = tree(prefix)
    result = run(prefix, '--', 'game')
    during = (prefix / 'during.txt').read_text()
    (prefix / 'during.txt').unlink()
    assert result.returncode == 5, result
    assert 'd3d9.dll -> ' in during and 'usr-lib-wiz3d/x64/d3d9.dll' in during, during
    assert 'd3d9_real.dll' in during and 'No such file' not in during.split('log dir')[0], during
    assert 'log dir: Z:' in during and 'logs' in during, during
    assert tree(prefix) == before, 'the prefix is not as it was after the game'
    print('PASS: placed for the game, both system folders; back byte for byte afterwards; exit status passed on')

    module = next(p for p in (LAUNCH.parent / 'wiz3d_prefix.py', LAUNCH.resolve().parent.parent / 'lib' / 'wiz3d' / 'python' / 'wiz3d_prefix.py') if p.exists())

    def prefix_tool(action, target):
        env = dict(os.environ, WIZ3D_DIR=str(wiz3d))
        subprocess.run([sys.executable, '-I', str(module), action, str(target)], env=env, check=True)

    # A game that was killed leaves wiz3D in the prefix: the next launch with the switch off takes it out.
    prefix_tool('on', prefix)
    prefix_tool('on', prefix)
    assert tree(prefix) != before and (prefix / 'drive_c/windows/system32/d3d9_real.dll').read_bytes() == b'MZ DXVK_HUD d3d9 x64'
    result = run(prefix, '--disable-3d', '--', 'true')
    assert result.returncode == 0 and tree(prefix) == before, result
    print('PASS: placing twice is harmless; a leftover is removed by the next launch with 3D off')
    prefix_tool('on', prefix)
    result = run(prefix, '--', 'true', WIZ3D_ENABLE_3D='0')
    assert result.returncode == 0 and tree(prefix) == before and not (prefix / 'during.txt').exists(), result
    print('PASS: WIZ3D_ENABLE_3D=0 restores the prefix and runs the game without wiz3D')

    # DXVK in one folder only: wiz3D goes where DXVK is, and the other folder is said and left alone.
    half = make_prefix('half')
    (half / 'drive_c/windows/syswow64/d3d9.dll').write_bytes(b'MZ Wine placeholder DLL')
    half_before = tree(half)
    result = run(half, '--', 'game')
    during = (half / 'during.txt').read_text()
    (half / 'during.txt').unlink()
    listed = [line for line in during.splitlines() if line.startswith(('-rw', 'lrw'))]
    assert len(listed) == 2 and all('system32' in line for line in listed), during
    assert 'no DXVK in' in result.stderr and 'syswow64' in result.stderr, result
    assert tree(half) == half_before
    print('PASS: DXVK in one system folder only: wiz3D goes there, the other is said and left alone, the prefix comes back')

    # DXVK is needed: a prefix with Wine's own Direct3D is refused, before anything is changed.
    plain = make_prefix('plain', dxvk=False)
    plain_before = tree(plain)
    result = run(plain, '--', 'game')
    assert result.returncode != 0 and 'needs DXVK' in result.stderr and 'turn DXVK on' in result.stderr, result
    assert tree(plain) == plain_before and not (plain / 'during.txt').exists()
    print('PASS: a prefix without DXVK is refused with the reason, and left alone')

    result = subprocess.run([str(LAUNCH), '--', 'game'], env={k: v for k, v in os.environ.items() if k != 'WINEPREFIX'}, capture_output=True, text=True)
    assert result.returncode != 0 and 'WINEPREFIX' in result.stderr
    print('PASS: without WINEPREFIX it says what it needs')

    # A 32-bit prefix (WINEARCH=win32): system32 is x86, there is no syswow64, and the x86 tree is what goes in.
    win32 = make_prefix('win32', arch='win32')
    win32_before = tree(win32)
    result = run(win32, '--', 'game')
    during = (win32 / 'during.txt').read_text()
    (win32 / 'during.txt').unlink()
    assert result.returncode == 5, result
    assert 'system32/d3d9.dll -> ' in during and 'usr-lib-wiz3d/x86/d3d9.dll' in during, during
    assert not (win32 / 'drive_c/windows/syswow64').exists() and 'no DXVK in' not in result.stderr, result
    assert tree(win32) == win32_before, 'the 32-bit prefix is not as it was after the game'
    print('PASS: a win32 prefix takes the x86 tree in system32, nothing else is made, and it comes back byte for byte')

    # Paths handed to the Windows side follow the prefix's drives, as Wine names them; without a drive, Wine's \\?\unix form.
    sys.path.insert(0, str(module.parent))
    import wiz3d_prefix
    assert wiz3d_prefix.arch(prefix) == 'win64' and wiz3d_prefix.arch(win32) == 'win32'
    assert wiz3d_prefix.windows_path(logs, prefix) == 'Z:' + str(logs).replace('/', '\\'), wiz3d_prefix.windows_path(logs, prefix)
    sandboxed = make_prefix('sandboxed', drives=())
    assert wiz3d_prefix.windows_path(logs, sandboxed) == '\\\\?\\unix' + str(logs).replace('/', '\\'), wiz3d_prefix.windows_path(logs, sandboxed)
    (sandboxed / 'dosdevices' / 'd:').symlink_to(logs)
    assert wiz3d_prefix.windows_path(logs / 'wiz3D_proxy.log', sandboxed) == 'D:\\wiz3D_proxy.log'
    assert wiz3d_prefix.windows_path(sandboxed / 'drive_c' / 'users', sandboxed) == 'C:\\users'
    result = run(sandboxed, '--', 'game')
    during = (sandboxed / 'during.txt').read_text()
    (sandboxed / 'during.txt').unlink()
    assert 'log dir: D:\\' in during, during
    print('PASS: paths follow the prefix\'s drives (longest folder, lowest letter) and need no Z: drive')

    # Debian's Python, not the first python3 on PATH: a conda environment in front must not change what the launchers import.
    foreign = temp / 'foreign-bin'
    foreign.mkdir()
    (foreign / 'python3').write_text('#!/bin/sh\necho "foreign python3 ran" >&2\nexit 99\n')
    (foreign / 'python3').chmod(0o755)
    path = str(foreign) + ':' + os.environ['PATH']
    result = run(prefix, '--disable-3d', '--', 'true', PATH=path)
    assert result.returncode == 0 and 'foreign' not in result.stderr, result
    result = subprocess.run([str(LAUNCH.with_name('wiz3d-run')), '--disable-3d', '--', 'true'], env=dict(os.environ, PATH=path), capture_output=True, text=True)
    assert result.returncode == 0 and 'foreign' not in result.stderr, result
    print('PASS: wiz3d-launch and wiz3d-run run on /usr/bin/python3 with a foreign python3 first on PATH')

    # The game runs in the folder of its .exe, as its Windows shortcut would (TrackMania quits elsewhere).
    folder = temp / 'Games' / 'Some Game'
    folder.mkdir(parents=True)
    (folder / 'game.exe').write_bytes(b'MZ')
    result = run(prefix, '--', 'wine', str(folder / 'game.exe'))
    during = (prefix / 'during.txt').read_text()
    (prefix / 'during.txt').unlink()
    assert result.returncode == 5 and f'cwd: {folder}' in during, during
    result = run(prefix, '--', 'wine', 'game.exe')
    during = (prefix / 'during.txt').read_text()
    (prefix / 'during.txt').unlink()
    assert f'cwd: {os.getcwd()}' in during, during
    print("PASS: the game runs in its .exe's folder when named by path, and where the user is otherwise")

    # A 32-bit game that does not run in the 64-bit prefix runs in a 32-bit one beside it, made then and remembered.
    # Wine and dxvk-setup are stand-ins: "wine" fails fast with Wine's own words in the 64-bit prefix and runs in the
    # 32-bit one; "wine32 wineboot" makes the prefix skeleton; both record their calls.
    fake = temp / 'fake-bin'
    fake.mkdir()
    (fake / 'wine').write_text('#!/bin/sh\necho "wine $WINEPREFIX $*" >> "$FAKE_LOG"\n'
                               'case "$WINEPREFIX" in *-win32) sleep "${FAKE_WIN32_SECONDS:-0}"; exit "${FAKE_WIN32_STATUS:-0}";; esac\n'
                               'echo "${FAKE_SAY:-}" >&2\nsleep "${FAKE_SECONDS:-0}"\nexit "${FAKE_STATUS:-0}"\n')
    (fake / 'wine32').write_text('#!/bin/sh\necho "wine32 $WINEPREFIX $*" >> "$FAKE_LOG"\n'
                                 'if [ "$1" = wineboot ]; then mkdir -p "$WINEPREFIX/drive_c/windows/system32" "$WINEPREFIX/dosdevices"\n'
                                 '  printf "WINE REGISTRY Version 2\\n;; All keys relative to \\\\\\\\Machine\\n\\n#arch=win32\\n\\n" > "$WINEPREFIX/system.reg"\n'
                                 '  ln -s "$WINEPREFIX/drive_c" "$WINEPREFIX/dosdevices/c:"; ln -s / "$WINEPREFIX/dosdevices/z:"; fi\nexit 0\n')
    (fake / 'dxvk-setup').write_text('#!/bin/sh\necho "dxvk-setup $WINEPREFIX $*" >> "$FAKE_LOG"\nprintf "MZ DXVK_HUD d3d9 x86" > "$WINEPREFIX/drive_c/windows/system32/d3d9.dll"\n')
    (fake / 'wineserver').write_text('#!/bin/sh\nexit 0\n')
    for name in ('wine', 'wine32', 'dxvk-setup', 'wineserver'):
        (fake / name).chmod(0o755)
    fake_log = temp / 'fake.log'
    state = temp / 'state'
    pe = b'MZ' + bytes(0x3a) + (0x40).to_bytes(4, 'little') + b'PE\0\0' + (0x14c).to_bytes(2, 'little') + bytes(20)
    game32 = temp / 'Games' / 'Old Game' / 'old.exe'
    game32.parent.mkdir(parents=True)
    game32.write_bytes(pe)
    sixtyfour = make_prefix('p64')

    def launch(prefix, *args, **env):
        fake_log.write_text('')
        full = dict(PATH=str(fake) + ':' + os.environ['PATH'], FAKE_LOG=str(fake_log), XDG_STATE_HOME=str(state), WIZ3D_WINETRICKS='0', WINEDEBUG='-all')
        full.update(env)
        return run(prefix, *args, **full)

    result = launch(sixtyfour, '--disable-3d', '--', 'wine', str(game32), FAKE_SAY='00dc:err:module:loader_init "krnl386.exe16" failed to initialize, aborting', FAKE_STATUS='5')
    calls = fake_log.read_text()
    other = str(sixtyfour) + '-win32'
    assert result.returncode == 0, result
    assert 'does not run in the 64-bit prefix' in result.stderr and 'krnl386.exe16' in result.stderr and 'made now' in result.stderr, result.stderr
    assert f'wine {sixtyfour} ' in calls and f'wine32 {other} wineboot' in calls and f'dxvk-setup {other}' in calls and f'wine {other} ' in calls, calls
    assert (Path(other) / 'system.reg').read_text().count('#arch=win32') == 1
    assert 'remembered for' in result.stderr and (state / 'wiz3d' / 'prefixes.json').exists(), result.stderr
    print('PASS: a 32-bit game that fails in the 64-bit prefix with Wine\'s words runs in a 32-bit prefix made beside it, and the choice is remembered')

    result = launch(sixtyfour, '--disable-3d', '--', 'wine', str(game32), FAKE_STATUS='5')
    calls = fake_log.read_text()
    assert result.returncode == 0 and 'chosen on' in result.stderr and f'wine {sixtyfour} ' not in calls and f'wine {other} ' in calls, (result.stderr, calls)
    print('PASS: the next launch goes straight to the remembered 32-bit prefix and says why')

    result = launch(sixtyfour, '--disable-3d', '--', 'wine', str(game32), FAKE_STATUS='5', WIZ3D_FALLBACK='0')
    calls = fake_log.read_text()
    assert result.returncode == 5 and f'wine {sixtyfour} ' in calls and f'wine {other} ' not in calls and 'prefix' not in result.stderr, (result, calls)
    print('PASS: WIZ3D_FALLBACK=0 runs the game where it was asked and passes its status on')

    (state / 'wiz3d' / 'prefixes.json').unlink()
    result = launch(sixtyfour, '--disable-3d', '--', 'wine', str(game32), FAKE_STATUS='0')
    calls = fake_log.read_text()
    assert result.returncode == 0 and f'wine {other} ' not in calls and 'prefix' not in result.stderr, (result, calls)
    print('PASS: a quick end with status 0 and nothing said is not a failure (TrackMania from the wrong folder): no fallback')

    result = launch(sixtyfour, '--disable-3d', '--', 'wine', str(game32), FAKE_STATUS='3', FAKE_WIN32_STATUS='3')
    calls = fake_log.read_text()
    assert result.returncode == 3 and f'wine {other} ' in calls and 'either' in result.stderr and not (state / 'wiz3d' / 'prefixes.json').exists(), (result.stderr, calls)
    print('PASS: a quick bad status tries the 32-bit prefix; when that fails too, it says so and remembers nothing')

    game64 = game32.with_name('new64.exe')
    game64.write_bytes(pe.replace((0x14c).to_bytes(2, 'little'), (0x8664).to_bytes(2, 'little')))
    result = launch(sixtyfour, '--disable-3d', '--', 'wine', str(game64), FAKE_STATUS='3')
    calls = fake_log.read_text()
    assert result.returncode == 3 and f'wine {other} ' not in calls and 'prefix' not in result.stderr, (result, calls)
    print('PASS: a 64-bit game never moves to a 32-bit prefix')

    ne = b'MZ' + bytes(0x3a) + (0x40).to_bytes(4, 'little') + b'NE' + bytes(20)
    game16 = game32.with_name('setup16.exe')
    game16.write_bytes(ne)
    result = launch(sixtyfour, '--disable-3d', '--', 'wine', str(game16))
    calls = fake_log.read_text()
    assert result.returncode == 0 and '16-bit program' in result.stderr and f'wine {sixtyfour} ' not in calls and f'wine {other} ' in calls, (result.stderr, calls)
    print('PASS: a 16-bit program goes to the 32-bit prefix from its header, without a failed run first')
    (state / 'wiz3d' / 'prefixes.json').unlink()

    # The game draws both eyes itself: wiz3D stays out, DXVK is told the packing, wiz3d-run declares the window.
    stub.write_text('#!/bin/sh\necho "run $*" > "$WINEPREFIX/during.txt"\nprintf "config: %s\\n" "$DXVK_CONFIG" >> "$WINEPREFIX/during.txt"\n'
                    'ls -l "$WINEPREFIX/drive_c/windows/system32/d3d9.dll" >> "$WINEPREFIX/during.txt"\n'
                    '[ -e "$WINEPREFIX/drive_c/windows/system32/S3DAPI.dll" ] && echo "S3DAPI present" >> "$WINEPREFIX/during.txt" || echo "S3DAPI absent" >> "$WINEPREFIX/during.txt"\nexit 0\n')
    result = run(prefix, '--native-stereo', 'top-and-bottom', '--right-eye-first', '--', 'game', DXVK_CONFIG='dxvk.hud = fps')
    during = (prefix / 'during.txt').read_text()
    (prefix / 'during.txt').unlink()
    assert result.returncode == 0, result
    assert 'run --native-stereo -- game' in during, during
    assert 'config: dxvk.hud = fps; dxvk.stereoInput = topAndBottom; dxvk.stereoInputRightFirst = True' in during, during
    assert 'S3DAPI absent' in during and 'd3d9.dll -> ' not in during, during
    assert tree(prefix) == before
    result = run(prefix, '--native-stereo', 'sideways', '--', 'game')
    assert result.returncode != 0 and 'sideBySide' in result.stderr and 'checkerboard' in result.stderr, result.stderr
    print('PASS: --native-stereo keeps wiz3D out, names the packing to DXVK and wiz3d-run, and lists the layouts for a wrong one')
