# Container image to run the wiz3D DX9 chain under Wine + DXVK, headless.
# debian:trixie + Wine (testing currently carries no wine package) (64 and 32 bit) + Xvfb + Mesa lavapipe (Vulkan
# software rasterizer) + DXVK from its release tarball.
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386 \
 && apt-get update -qq && apt-get install -y --no-install-recommends \
    wine64 wine32:i386 wine \
    xvfb x11-utils xauth \
    mesa-vulkan-drivers mesa-vulkan-drivers:i386 \
    vulkan-tools \
    python3 python3-pil python3-numpy \
    ca-certificates curl xz-utils bzip2 \
    mingw-w64 \
 && rm -rf /var/lib/apt/lists/*
# DXVK release tarball: x64 and x32 d3d9.dll into the image.
ARG DXVK_VERSION=2.7.1
RUN curl -fsSL https://github.com/doitsujin/dxvk/releases/download/v${DXVK_VERSION}/dxvk-${DXVK_VERSION}.tar.gz \
    -o /tmp/dxvk.tar.gz \
 && mkdir -p /opt/dxvk && tar -xz -C /opt/dxvk --strip-components=1 -f /tmp/dxvk.tar.gz \
 && rm /tmp/dxvk.tar.gz \
 && ls /opt/dxvk/x64/d3d9.dll /opt/dxvk/x32/d3d9.dll
ENV WINEARCH=win64
