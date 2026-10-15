# Sparky Stereo OS packaging notes

Target: Sparky Stereo OS 9 “Mashtabba”, based on Debian 14 “Forky”.
This is a patched upstream package, not a replacement for Sparky's own tools.
The partner workspace produces DLLs and a launcher; it does not publish a Debian package.

Suggested package layout:

| Location | Contents |
|---|---|
| `/usr/lib/wiz3d/x64/` | x64 runtime tree produced by build-linux.sh |
| `/usr/lib/wiz3d/x86/` | x86 runtime tree produced by build-linux.sh |
| `/usr/bin/wiz3d-run` | tools/proton/wiz3d-run: runs a game and declares its window |
| `/usr/bin/wiz3d-launch` | tools/proton/wiz3d-launch: a Wine prefix made when missing, wiz3D placed in it beside DXVK for the run, the game run in its own folder |
| `/usr/lib/wiz3d/python/wiz3d_prefix.py` | the prefix module of wiz3d-launch (architecture from system.reg, drive paths as Wine names them, creation) |
| `/usr/share/doc/wiz3d/` | README, these notes, licence texts and provenance |

Two ways to opt a game in.
With Steam and Proton: copy the matching architecture's runtime tree into the game's executable directory and use the launch option `WINEDLLOVERRIDES="d3d9=n,b" wiz3d-run -- %command%`.
With a Wine prefix: `WINEPREFIX=... wiz3d-launch -- wine game.exe`; the proxy goes into the prefix's system folder in front of DXVK (DXVK's d3d9.dll kept as d3d9_real.dll, the rest links into /usr/lib/wiz3d), and comes out again when the game ends, so the prefix and the game folder are byte for byte as they were.
A 32-bit prefix (WINEARCH=win32) gets the x86 tree in system32; a 64-bit one x64 in system32 and x86 in syswow64.
A missing prefix is made by wiz3d-launch: wineboot for WINEARCH, the system's DXVK through dxvk-setup, Microsoft's d3dx9 and d3dcompiler_43 through winetricks when installed, the user folders inside the prefix, no menu entries, Z: kept.
Removal of the package leaves every game folder and prefix as it was.
No root privilege is needed for per-game opt-in.

Runtime dependencies: Python 3, the shared `stereo_declare` module (package python3-stereo-declare, from the libstereo-declare source: it brings python3-xlib and `libstereo-declare.so.1`), and KWin with X11 declaration support version 2.
Display settings additionally needs `kcmshell6` and `kcm_kscreen`.
Use the edition's shared helper package rather than vendoring a second declaration implementation.
Final Debian package names for that new library belong to the shared helper's packager.
Wine and DXVK are supplied by Proton, or by the edition's wine and dxvk packages for a prefix (the package depends on dxvk 2.7.1-4+stereo3d2 for dxvk-setup with 32-bit prefixes, and recommends the edition's wine, whose launcher picks wine32 for a 32-bit prefix, and winetricks).
Microsoft's d3dx9 and d3dcompiler_43 are needed by games whose HLSL Wine's own compiler refuses (TrackMania Nations Forever); the package does not ship them, wiz3d-launch adds them through winetricks when it makes a prefix.

Ship the repository's `LICENSE` (LGPL 2.1) and `LICENSE-iZ3D.txt` (MIT) verbatim.
The Linux staging step copies both alongside the runtime.
Preserve the iZ3D, wiz3D/effcol and Bo3b notices already in the source, and include the linked third-party libraries' licence/notice files in the final distribution.
The shared declaration helper has its own MIT licence.
Provide the exact fork revision and complete corresponding source, including build scripts and the vendored inputs needed to rebuild.
Do not distribute the xwin SDK/ATL download or a Wine prefix as part of this package.
This task verifies the two project licence files in the staging tree; it is not a completed third-party packaging audit or an installer/repository publication.

Use upstream version plus `+stereo3dN`, retaining the fork and revision in the source metadata.
Edition package provenance follows the packaging skill:

- Maintainer: Daniel Ramos (Capitain Jack) <Capitain_Jack@yahoo.com>
- Homepage: https://sparkylinux.org
- Preserve an upstream package's maintainer as Original-Maintainer if adapting existing packaging.
- Credit: Sparky Stereo OS, an edition of SparkyLinux, created by Paweł “pavroo” Pijanowski and Daniel Ramos (Capitain Jack).

No package, repository, ISO, signing key, host installation, Steam files, or running compositor was changed by this work.
Container tests cover the runtime layout, full-SBS frames, declaration contract, disabled state, and launcher; `tools/proton/test-launch.py` the prefix placement, both architectures, the drive paths and the working folder; `tools/proton/test-prefix.sh` the prefix creation with real Wine.
Actual edition installation and Steam/Proton validation remain release checks.
