#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Run in a private Xvfb with the installed shared declaration library."""
import importlib.machinery
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from Xlib import X, Xatom, display

RUN = Path(os.environ.get('WIZ3D_TEST_RUN') or Path(__file__).with_name('wiz3d-run'))
module = importlib.machinery.SourceFileLoader('launcher', str(RUN)).load_module()
x = display.Display()
root = x.screen().root
support = x.intern_atom('_KDE_NET_WM_STEREO_CONTENT_SUPPORTED')
layout = x.intern_atom('_KDE_NET_WM_STEREO_CONTENT')
kind = x.intern_atom('_KDE_NET_WM_STEREO_CONTENT_CLASS')
root.delete_property(support)
x.sync()
try:
    module.Declaration()
except RuntimeError:
    print('PASS: unsupported compositor rejected')
else:
    raise AssertionError('unsupported compositor accepted')
root.change_property(support, Xatom.CARDINAL, 32, [2])
x.sync()
d = module.Declaration()
assert d.version == 2
d.close()
root.change_property(support, Xatom.CARDINAL, 32, [3])
x.sync()
d = module.Declaration()
assert d.version == 3
d.close()
root.change_property(support, Xatom.CARDINAL, 32, [2])
x.sync()
d = module.Declaration()
print('PASS: declaration support version read from the root')


def window(width=1600, pid=os.getpid(), name='test.exe'):
    w = root.create_window(0, 0, width, 600, 0, x.screen().root_depth, X.InputOutput, X.CopyFromParent)
    w.set_wm_class(name, name)
    w.change_property(x.intern_atom('_NET_WM_PID'), Xatom.CARDINAL, 32, [pid])
    w.map()
    x.sync()
    return w


def read(w, atom):
    p = w.get_full_property(atom, X.AnyPropertyType)
    if p is not None:
        assert p.property_type == Xatom.CARDINAL and p.format == 32
        return list(p.value)
    return None


valid = window()
wrong_size = window(width=800)
wrong_pid = window(pid=2147483647)
wrong_class = window(name='other.exe')
state = (1600, 600, 'test.exe', 0)
assert d.candidates(state, {os.getpid()}, None) == {valid.id}
assert d.candidates(None, {os.getpid()}, None) == set()
d.update({valid.id})
assert read(valid, layout) == [3] and read(valid, kind) == [3, 3]
for other in [wrong_size, wrong_pid, wrong_class]:
    assert read(other, layout) is None
print('PASS: class, process, geometry, and plugin state gate declaration')
valid.destroy()
x.sync()
replacement = window()
d.update(d.candidates((1600, 600, "test.exe", replacement.id), set(), None))
assert read(replacement, layout) == [3] and read(replacement, kind) == [3, 3]
print('PASS: replacement window redeclared')
replacement.configure(width=1200)
x.sync()
assert d.candidates((1600, 600, 'test.exe', replacement.id), set(), None) == {replacement.id}
print('PASS: known native window retains declaration when resized')
d.update(set())
assert read(replacement, layout) is None and read(replacement, kind) is None
print('PASS: declaration removed')
d.close()
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / 'state'
    path.write_text('wiz3d-full-sbs-v1 1600 600 0\ntest.exe\n')
    assert module.window_state(path) == state
    path.write_text('wiz3d-full-sbs-v1 1601 600 0\ntest.exe\n')
    assert module.window_state(path) is None
    path.write_text('partial')
    assert module.window_state(path) is None
    # Test the shortcut by intercepting its executable, not by starting KScreen.
    fake = Path(temp) / 'kcmshell6'
    fake.write_text('#!/bin/sh\n[ "$#" = 1 ] && [ "$1" = kcm_kscreen ]\n')
    fake.chmod(0o755)
    env = dict(os.environ, PATH=temp + ':' + os.environ['PATH'])
    subprocess.run([str(RUN), '--display-settings'], env=env, check=True)
print('PASS: state parsing and Display settings shortcut')
result = subprocess.run([str(RUN), '--disable-3d', '--', 'sh', '-c', 'exit 7'])
assert result.returncode == 7
print('PASS: game exit status preserved')
result = subprocess.run([str(RUN), '--', 'true'])
assert result.returncode == 1
print('PASS: missing packed game window cannot report success')
x.close()
