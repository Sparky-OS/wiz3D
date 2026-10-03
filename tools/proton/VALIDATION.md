# Container verification, 2026-10-03

These results cover the DX9 build and X11 declaration contract. They do not
claim verification on a host GPU, Steam, Proton, or a running KWin desktop.

Environment: Debian testing clang-cl/lld-link/xwin cross build, x64 and x86;
Wine 10.0, DXVK 2.7.1 release DLL, Debian trixie Mesa lavapipe, private Xvfb.
Every build/test container is limited to four CPUs. No host display socket,
GPU node, Steam directory, or compositor is mounted.

The exact staged configuration also passed a separate full-SBS/declaration run
without the test harness's configuration overrides.

The full suite's analytic expectation is
`eye_width / 2 * separation * (0.5 - 1/z)`, for z=4, 1000, 2.

| Test | Measured | Expected/result |
|---|---|---|
| Half SBS, S=.16 | 8, 15.5, 0 px | 8, 15.968, 0 px |
| Half SBS, S=.08 | 4, 7.5, 0 px | 4, 7.984, 0 px |
| Full SBS, 400x300/eye | 8, 15, 0 px | 8, 15.968, 0 px |
| Full SBS, 800x600/eye | 16, 31, 0 px | 16, 31.936, 0 px |
| Full SBS, 1200x900/eye | 24, 47, 0 px | 24, 47.904, 0 px |
| Reset, auto width and height | 1600x600 | Same full-SBS parallax |
| Reset, auto width only | 1600x600 | Same full-SBS parallax |
| Fullscreen request | 1600x600 window | Same full-SBS parallax |
| Enable 3D off | 800x600 mono | No stereo declaration |
| X11 declaration | CARDINAL/32 [3], [3,3] | Full SBS, game/GL wrapper |

The image oracle allows one pixel for rasterization. It also checks every
marker's position and width in both eyes, rejecting black, missing, identical,
reversed, and wrong-separation frames. PNGs were generated from X11 captures
and visually inspected. In-process backbuffer readback is diagnostic only.

The first auto-size reset failed at 3200x600; the fixed code returns 1600x600.
The first process-tree watcher missed Wine's reparented game. The working bridge
uses the tested native `__wine_x11_whole_window` XID; arbitrary Wine SetProp
mirroring fails its separate test and is not used.

Launcher checks cover compositor-support rejection, unrelated class/PID/size
filtering, exact native-window targeting, replacement, resize, removal of both
properties, malformed state, child exit status, absent packed-window failure,
and the Display settings executable/argument via a stub. DX10 rejects mode 3
rather than silently interpreting the DX9-only mode as another layout.

Build checks cover both architectures, recorded header dependencies, expected
runtime layout/configuration and byte-identical copies of the repository's
MIT and LGPL 2.1 licence texts. A clean build and its runtime suite passed.

Reproduce with `tools/run-wine/modes-test.sh` and `tools/proton/test.sh` as
explained in their READMEs. `WIZ3D_TEST_DLL_DIR` can select the x64 directory
from a separate clean build. Run check-package.py with repository and staged
output paths inside a container. The workspace-level REPORT.md lists the logs,
image paths, decisions, and exact working commits for the partner review.

Not verified: x86 runtime, MSVC, real Proton or games, native Wine Wayland,
multiple simultaneous primary swapchains, KWin fullscreen/pointer behavior,
GPU performance or /Ob0 cost, installed Debian packaging, and the complete
third-party redistribution audit. The brief's packaging deliverable is notes.
