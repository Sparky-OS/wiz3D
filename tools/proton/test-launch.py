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
                    'printf "log dir: %s\\n" "$WIZ3D_LOG_DIR" >> "$WINEPREFIX/during.txt"\nexit 5\n')
    stub.chmod(0o755)

    def make_prefix(name, dxvk=True):
        prefix = temp / name
        for folder, arch in (('system32', 'x64'), ('syswow64', 'x86')):
            (prefix / 'drive_c' / 'windows' / folder).mkdir(parents=True)
            body = b'MZ DXVK_HUD d3d9 ' + arch.encode() if dxvk else b'MZ Wine placeholder DLL'
            (prefix / 'drive_c' / 'windows' / folder / 'd3d9.dll').write_bytes(body)
            (prefix / 'drive_c' / 'windows' / folder / 'dxgi.dll').write_bytes(b'dxgi')
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
