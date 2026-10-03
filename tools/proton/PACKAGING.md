# Sparky Stereo OS packaging notes

Target: Sparky Stereo OS 9 “Mashtabba”, based on Debian 14 “Forky”. This is a
patched upstream package, not a replacement for Sparky's own tools. The partner
workspace produces DLLs and a launcher; it does not publish a Debian package.

Suggested package layout:

| Location | Contents |
|---|---|
| `/usr/lib/wiz3d/x64/` | x64 runtime tree produced by build-linux.sh |
| `/usr/lib/wiz3d/x86/` | x86 runtime tree produced by build-linux.sh |
| `/usr/bin/wiz3d-run` | tools/proton/wiz3d-run |
| `/usr/share/doc/wiz3d/` | README, these notes, licence texts and provenance |

Copy the matching architecture's runtime tree into each opted-in game's
executable directory. Do not install proxies globally in Wine prefixes. Steam
launch option: `WINEDLLOVERRIDES="d3d9=n,b" wiz3d-run -- %command%`.
Removal: remove that launch option and only the files installed for wiz3D,
restoring any prior DLL/configuration backups. The launcher never installs or
rewrites game files. No root privilege is needed for per-game opt-in.

Runtime dependencies: Python 3, python3-xlib, libX11, the shared
`libstereo-declare.so.1` (ABI 1), and KWin with X11 declaration support version 2.
Display settings additionally needs `kcmshell6` and `kcm_kscreen`. Use the
edition's shared helper package rather than vendoring a second declaration
implementation. Final Debian package names for that new library belong to the
shared helper's packager. Wine/DXVK are supplied by Proton or a configured Wine
prefix. Builtin `d3dx9_43` is needed; the package does not ship Microsoft's DLL.

Ship the repository's `LICENSE` (LGPL 2.1) and `LICENSE-iZ3D.txt` (MIT) verbatim.
The Linux staging step copies both alongside the runtime. Preserve the iZ3D,
wiz3D/effcol and Bo3b notices already in the source, and include the linked
third-party libraries' licence/notice files in the final distribution. The
shared declaration helper has its own MIT licence. Provide the exact fork
revision and complete corresponding source, including build scripts and the
vendored inputs needed to rebuild. Do not distribute the xwin SDK/ATL download
or a Wine prefix as part of this package. This task verifies the two project
licence files in the staging tree; it is not a completed third-party packaging
audit or an installer/repository publication.

Use upstream version plus `+stereo3dN`, retaining the fork and revision in the
source metadata. Edition package provenance follows the packaging skill:

- Maintainer: Daniel Ramos (Capitain Jack) <Capitain_Jack@yahoo.com>
- Homepage: https://sparkylinux.org
- Preserve an upstream package's maintainer as Original-Maintainer if adapting
  existing packaging.
- Credit: Sparky Stereo OS, an edition of SparkyLinux, created by Paweł
  “pavroo” Pijanowski and Daniel Ramos (Capitain Jack).

No package, repository, ISO, signing key, host installation, Steam files, or
running compositor was changed by this work. Container tests cover the runtime
layout, full-SBS frames, declaration contract, disabled state, and launcher.
Actual edition installation and Steam/Proton validation remain release checks.
