# Headless DX9 verification

Build DLLs with `./build-linux.sh all`. Build the test image with
`DOCKER_BUILDKIT=0 docker build --cpu-quota=400000 -t wiz3d-wine-test tools/run-wine`.
Run `tools/run-wine/modes-test.sh /absolute/workspace/new-evidence-directory`.
The Docker socket is selected by the caller's `DOCKER_HOST`.

Only the workspace is mounted, with four CPUs and no display sockets or GPU
nodes. The runtime image uses Debian trixie because the initial testing image
could not install Wine. The build image remains Debian testing. Wine 10.0 uses
DXVK 2.7.1 from its release tarball, Xvfb, and Mesa's lavapipe Vulkan ICD.
The probe is x64. x86 DLL compilation is a separate build check.

`frame.png` comes from the actual X11 client window. The optional in-process
backbuffer dump is diagnostic only: the wrapper exposes the application's
backbuffer, which need not be the composed output. The loader trace must contain
the native output plug-in and DXVK, and the proxy log must show wrapper routing.

Three equally sized screen markers use an identity view, projection _11=1,
and depths 4, 1000, and 2. At convergence 1/ZPS=0.5 and separation S, the
right-minus-left disparity is `eye_width / 2 * S * (0.5 - 1/z)`.
Half SBS has eye_width=400. S=0.16 predicts 8, 15.968, and 0 pixels;
S=0.08 predicts 4, 7.984, and 0. The checker permits one pixel for rasterization,
checks both markers' positions and sizes, and rejects missing or identical eyes.
Run `check-negative.py path/to/half/frame.xwd` inside the image to assert
rejection of black, missing, identical, reversed, and wrong-separation cases.

The probe also verifies a Win32 `__wine_x11_WIZ3D_TEST` property locally and
checks that no `WIZ3D_TEST` X atom appeared. Wine 10.0 does not mirror this
arbitrary property. Stereo declaration therefore belongs in a Linux launcher.
