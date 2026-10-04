#!/usr/bin/env python3
"""Check the presented X11 image against the probe camera's analytic result."""
import argparse
import struct
import numpy as np
from PIL import Image


def read_xwd(path):
    data = open(path, 'rb').read()
    h = struct.unpack('>25I', data[:100])
    size, version, fmt, depth, width, height = h[:6]
    order, bpp, stride, masks, ncolors = h[7], h[11], h[12], h[14:17], h[19]
    if version != 7 or fmt != 2 or bpp != 32 or depth != 24:
        raise ValueError('expected Xvfb 24-bit TrueColor ZPixmap in 32-bit pixels')
    pixels = np.frombuffer(data, dtype='<u4' if order == 0 else '>u4',
                           offset=size + ncolors * 12).reshape(height, stride // 4)[:, :width]
    channels = []
    for mask in masks:
        shift = (mask & -mask).bit_length() - 1
        channels.append(((pixels & mask) >> shift) * 255 // (mask >> shift))
    return np.stack(channels, axis=-1).astype(np.uint8)


def check(img, mode, separation, render_width=800, render_height=600):
    width = render_width * (2 if mode == 'full' else 1)
    assert img.shape == (render_height, width, 3), f'wrong frame dimensions: {img.shape}'
    eye_width = width if mode == 'mono' else width // 2
    stereo = mode != 'mono'
    if stereo and separation:
        assert not np.array_equal(img[:, :eye_width], img[:, eye_width:]), 'identical halves'
    # CBaseStereoRenderer::CalculateFPMatrix: each camera adds +/- S/2*(1/z-C)
    # to clip x / w. Viewport maps NDC x to (x+1)*eye_width/2. D3D9 pixel
    # centers are integral; an edge at an integer leaves centroid -0.5.
    for name, channel, x, z in [('red', 0, -.6, 4), ('green', 1, -30, 1000),
                                ('blue', 2, .5, 2)]:
        centers = []
        for eye in range(2 if stereo else 1):
            half = img[:, eye * eye_width:(eye + 1) * eye_width].astype(int)
            mask = (half[..., channel] > 180)
            for other in range(3):
                if other != channel:
                    mask &= half[..., other] < 100
            ys, xs = np.nonzero(mask)
            assert len(xs) >= max(8, eye_width * render_height * .0004), f'{name} eye {eye}: missing or undersized marker ({len(xs)})'
            ndc_shift = (1 if eye == 0 else -1) * separation / 2 * (1 / z - .5) if stereo else 0
            expected = (1 + x / z + ndc_shift) * eye_width / 2 - .5
            center = float(xs.mean())
            assert abs(center - expected) <= 1, f'{name} eye {eye}: center {center} != {expected}'
            marker_width = int(xs.max() - xs.min() + 1)
            assert abs(marker_width - eye_width * .025) <= 1, f'{name}: wrong marker width {marker_width}'
            assert abs(float(ys.mean()) - (render_height / 2 - .5)) <= 1, f'{name}: wrong vertical position'
            centers.append(center)
        if stereo:
            expected = eye_width / 2 * separation * (.5 - 1 / z)
            disparity = centers[1] - centers[0]
            assert abs(disparity - expected) <= 1, f'{name}: disparity {disparity} != {expected}'
            print(f'{name}: parallax={disparity:+.2f}px expected={expected:+.2f}px')
        else:
            print(f'{name}: mono center={centers[0]:.2f}px')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('frame')
    p.add_argument('png')
    p.add_argument('--mode', choices=['mono', 'half', 'full'], default='half')
    p.add_argument('--separation', type=float, default=.16)
    p.add_argument('--render-width', type=int, default=800)
    p.add_argument('--swapped', action='store_true', help='expect the eyes in the opposite places')
    p.add_argument('--render-height', type=int, default=600)
    a = p.parse_args()
    img = read_xwd(a.frame)
    Image.fromarray(img).save(a.png)
    if a.swapped:
        half = img.shape[1] // 2
        img = np.concatenate([img[:, half:], img[:, :half]], 1)
    check(img, a.mode, a.separation, a.render_width, a.render_height)
    print('PASS:', a.mode, img.shape)


if __name__ == '__main__':
    main()
