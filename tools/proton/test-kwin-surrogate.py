#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stand in for a game under wiz3d-run on a real KWin: one-view X11 window, the plug-in's state file, then report what KWin did."""
import os
import sys
import time
from Xlib import X, Xatom, display

d = display.Display()
root = d.screen().root
window = root.create_window(0, 0, 800, 600, 0, d.screen().root_depth, X.InputOutput, X.CopyFromParent)
window.set_wm_class('test.exe', 'test.exe')
window.change_property(d.intern_atom('_NET_WM_PID'), Xatom.CARDINAL, 32, [os.getpid()])
window.map()
d.sync()
state = os.environ.get('WIZ3D_STEREO_STATE')
if state and os.environ.get('WIZ3D_ENABLE_3D') == '1':
    path = state[2:].replace('\\', '/')
    with open(path + '.tmp', 'w') as f:
        f.write(f'wiz3d-full-sbs-v1 1600 600 {window.id}\ntest.exe\n')
    os.replace(path + '.tmp', path)
time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 4)
g = window.get_geometry()
layout = window.get_full_property(d.intern_atom('_KDE_NET_WM_STEREO_CONTENT'), X.AnyPropertyType)
print(f"SURROGATE: size={g.width}x{g.height} declared={list(layout.value) if layout else None} "
      f"enable={os.environ.get('WIZ3D_ENABLE_3D')} kwin_doubles={os.environ.get('WIZ3D_KWIN_DOUBLES')}", flush=True)
