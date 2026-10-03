# Proposed upstream contributions

These changes are on `partner/wiz3d-proton`. Nothing has been pushed or posted.
The original project's existing commits are left intact. Every new working
commit carries `Assisted-by: gpt-6-astra via Codex`, without Signed-off-by.

## Linux DX9 build

The build work is independent of the KWin mode: `38b0a413` (clang portability),
`4561e73d` (container build), `a490c7c3` (SIMD stores), `268e739a` (varargs), and
`c3902b5f` (remaining SIMD store and four-CPU build limit), and `ef41c822` (header dependency tracking). These use the existing MSVC-format vendor libraries with
clang-cl/lld-link and xwin's SDK/CRT/ATL. x64 and x86 build in Debian testing.
Leia and NVAPI stay outside the DX9 dependency chain.

The remaining /Ob0 workaround is explicit in gen_build.py. Removing it exposed
cross-translation-unit inline definitions in the earlier review. Performance
and a fresh MSVC build remain unverified. These limitations belong in the PR,
not hidden in a claim of cross-toolchain equivalence.

## Full side by side and Linux declaration

The new internal DX9 SideBySideOutput mode 3 reuses the existing span render
resources and composes two full eyes. It creates a doubled window, converts
exclusive-fullscreen requests to windowed presentation, ignores output gaps,
and preserves per-eye width when Reset asks for automatic dimensions. Existing
modes 0/1/2 remain available upstream; Linux staging fixes mode 3, with no
output-format picker in the launcher.

The Wine bridge writes native-window metadata to the launcher's private file;
the launcher calls the external MIT stereo-declare library. It does not
implement KWin's properties itself. Keep this integration separate from the
portable full-SBS rendering discussion if effcol prefers to maintain the Linux
launcher downstream. The declaration mode/class is full SBS / game / GL wrapper.
This new mode is DX9-only; it is not a promise about the plug-in's DX10 path.

## Evidence for review

The half-SBS suite compares the actual X11 frame against a known perspective
camera at two separation settings and rejects broken-frame controls. The
full-SBS suite checks three per-eye resolutions, two automatic-size reset
forms, mono opt-out, fullscreen-to-window fallback, native declaration readback,
and window replacement/removal. All build/run tests are container-only with
four CPUs and software rendering. See the test READMEs for reproducible commands.

Known limits: runtime x86, real Proton/Steam, Windows/MSVC, multiple primary
windows per launch, native Wine Wayland, arbitrary game resize handlers,
fullscreen placement and pointer behavior in real KWin, GPU performance, and
third-party redistribution packaging have not been verified. Do not describe
this patch set as tested compatibility with all Windows games.

Working series for the second contribution: `aae3b0ce` (DX9 output/reset/metadata),
`4243d125` (shared-helper launcher and Linux defaults), followed by the full-SBS
verification commit. Packaging and validation notes are kept in a separate commit.
