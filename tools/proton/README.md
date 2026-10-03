# wiz3D DX9 on Wine / Proton

This build gives KWin full side by side, left eye first. KWin chooses the
screen's output format in Display settings. The tested runtime is Wine 10.0
with DXVK 2.7.1 under Xvfb and Mesa lavapipe; Steam and Proton game runs have
not been tested here. This is a DX9 path, not DX11/DX12 support.

## Per-game setup

Build with `./build-linux.sh all`. Choose `out/x64` for a 64-bit game or
`out/x86` for a 32-bit game. Copy these files alongside the game's executable,
keeping the OutputMethods subdirectory:

```
d3d9.dll
S3DWrapperD3D9.dll
S3DAPI.dll
ZLOg.dll
OutputMethods/SideBySideOutput.dll
wiz3D_Config.xml
BaseProfile.xml
LICENSE
LICENSE-iZ3D.txt
```

Back up an existing proxy or configuration before replacing it. Do not mix
architectures or replace a prefix's DXVK DLL with wiz3D. The game-folder proxy
loads the wrapper beside itself; the wrapper loads system32's Direct3D, which
must be DXVK. Proton normally supplies DXVK and builtin D3DX9. A manual Wine
prefix needs both. The optional Leia SDK and NVAPI are not used by this build.

Install `wiz3d-run` on PATH, Python 3 with python-xlib, and the shared
`libstereo-declare.so.1` from plasma-wayland-protocols/stereo-declare. KWin must
advertise declaration version 2 on this X11/Xwayland display. Use this Steam
launch option:

```
WINEDLLOVERRIDES="d3d9=n,b" wiz3d-run -- %command%
```

The launcher adds the d3d9 override itself, so `wiz3d-run -- %command%` is also
sufficient. It passes the command as an argument vector, without a shell.
For a manual prefix: `wiz3d-run -- wine /path/to/game.exe`.
A bare `WINEDLLOVERRIDES="d3d9=n,b" %command%` loads the DLLs but needs a KWin
window rule to declare full SBS; it does not run the declaration helper.

## Controls

- **Enable 3D:** `wiz3d-run --enable-3d -- %command%` (the default).
  `--disable-3d` uses the mono wrapper for that launch and makes no declaration.
  This is a launch setting; restart the game to change it. The generated
  configuration disables the legacy stereo-toggle and eye-swap hotkeys.
- **Render resolution per eye:** the game's own render/video resolution.
  An 800×600 game renders each eye at 800×600 and presents a 1600×600 client.
  Choose a higher game resolution for sharpness or a lower one for frame rate;
  KWin scales each full eye to its displayed size. The default follows the
  game's window/backbuffer, or its selected fullscreen render resolution.
  The launcher prints the active per-eye size reported by the output plug-in.
- **Display settings:** `wiz3d-run --display-settings` runs
  `kcmshell6 kcm_kscreen`. Output formats belong there.

There is no output-format picker in this launcher. The config's output fields
are internal wiring for the plug-in; the Linux staging step fixes full SBS.
The game owns its render resolution and projection matrices. The launcher does
not claim to improve rendering quality by rescaling an already rendered image,
or force arbitrary render-target sizes into an unmodified game engine.

## Declaration bridge

The DLL cannot call Xlib. It reports its packed render size, executable name,
and `GetPropW(hwnd, L"__wine_x11_whole_window")` native window ID in a private
per-launch file supplied by `WIZ3D_STEREO_STATE`. This uses Wine's Z: mapping;
that mapping must exist. File replacement is atomic. Changed native IDs are
reported on subsequent frames, and the file is removed when the output object
is destroyed. No ELF executable is launched from Wine.

The Linux launcher checks that the X window is mapped and belongs to the
reported executable (or Steam application class), then calls the shared
`stereo_declare_x11(..., 3, 3, 3)` API: full SBS, game, GL wrapper. The shared
library owns the property names and payload. Without a native XID, the launcher
falls back to the Wine process tree and exact packed dimensions, or an explicit
`--steam-app-id ID`. It refuses ambiguous matches. The tested Wine start.exe
reparents the game quickly, so the native-XID route is preferred. SteamAppId
is used automatically when present.

Wine 10.0 returned the exact native XID in the test. Arbitrary
`SetProp("__wine_x11_NAME", ...)` was **not** mirrored to X11. Other Wine/Proton
versions and Wine's native Wayland driver are unverified. The current bridge
is for one primary DX9 swapchain per launch; multiple simultaneous game windows
need independent state records before they can be supported reliably.

Fullscreen requests are converted to a doubled window without changing the
screen mode. The test verifies the resulting full-SBS pixels and declaration;
real KWin fullscreen placement, cursor/menu interaction, real games' resize
handlers, anti-cheat, and Proton's fullscreen policies remain untested.

## Reproduce the checks

Run the half-SBS suite described in `../run-wine/README.md`. For the full suite,
build and install the shared helper into a directory in the workspace using
its own CMake instructions, inside a container. Mount its protocol source
read-only. Then build the test image:

```
DOCKER_BUILDKIT=0 docker build --cpu-quota=400000 \
  -f tools/proton/Dockerfile.test -t wiz3d-proton-test tools/proton
./tools/proton/test.sh /absolute/workspace/new-evidence /absolute/workspace/helper-install
```

It checks three per-eye resolutions, automatic-size reset, width-only automatic
reset, disabled 3D, fullscreen fallback, actual frame parallax, and X11 property
readback. The helper integration test exercises replacement, removal, unrelated
windows, malformed metadata, unsupported compositors, and the Display settings
command with a stub. These are Xvfb contract tests; they do not claim to run KWin.
