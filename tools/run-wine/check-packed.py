#!/usr/bin/env python3
"""Check the presented frame of probe_packed.exe: full side by side, left eye first, each eye at full size.

The probe draws the left eye as a red field with a white square and the right eye as a blue field with
the same square moved right by the disparity (grey fields for the anaglyphs); DXVK unpacks the packed
picture.  Expected: the window doubled (2 x width), the left half red (or the darker grey) with the square
at 3/10 of the eye's width, the right half blue (lighter grey) with the square DISPARITY pixels further
right, both squares at full size and at the same height.  With --packed the frame must be the packed
picture itself, one width wide, as the control that the unpacking is DXVK's doing."""
import argparse
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from check import read_xwd  # noqa: E402


def square(half, white=200):
    mask = np.all(half > white, axis=-1)
    ys, xs = np.nonzero(mask)
    assert len(xs) >= 64, f'no white square ({len(xs)} white pixels)'
    return float(xs.mean()), float(ys.mean()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def field(half, channel, white=200):
    """The share of the eye's pixels that are its field colour (outside the square)."""
    not_white = ~np.all(half > white, axis=-1)
    if channel in (0, 2):
        strong = (half[..., channel] > 120) & (half[..., (channel + 1) % 3] < 60) & (half[..., (channel + 2) % 3] < 60)
    else:  # grey: the three channels within 8 of each other and in the field's range
        spread = half.max(axis=-1).astype(int) - half.min(axis=-1).astype(int)
        strong = (spread <= 8) & (half[..., 0] > 20) & (half[..., 0] < 120)
    return float((strong & not_white).sum()) / max(1, float(not_white.sum()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xwd')
    parser.add_argument('--width', type=int, default=800)
    parser.add_argument('--height', type=int, default=600)
    parser.add_argument('--square', type=int, default=40)
    parser.add_argument('--disparity', type=int, default=32)
    parser.add_argument('--anaglyph', action='store_true', help='grey fields instead of red and blue')
    parser.add_argument('--packed', action='store_true', help='the control: the packed picture, not doubled')
    args = parser.parse_args()
    img = read_xwd(args.xwd).astype(int)
    if args.packed:
        assert img.shape == (args.height, args.width, 3), f'the control frame is {img.shape}, not the packed picture'
        print(f'control: the frame is the packed {args.width}x{args.height} picture, not doubled')
        return
    assert img.shape == (args.height, 2 * args.width, 3), f'wrong frame dimensions: {img.shape}'
    left, right = img[:, :args.width], img[:, args.width:]
    for name, half, channel in (('left', left, 0 if not args.anaglyph else 1), ('right', right, 2 if not args.anaglyph else 1)):
        share = field(half, channel)
        assert share > 0.97, f'{name} eye: the field is not {"red/blue" if not args.anaglyph else "grey"} ({share:.3f})'
    if args.anaglyph:
        assert left[0, 0, 0] < right[0, 0, 0], 'the left eye is not the darker field'
    lx, ly, lw, lh = square(left)
    rx, ry, rw, rh = square(right)
    expected_x = args.width * 3 / 10 - .5
    assert abs(lx - expected_x) <= 1.5, f'left square at {lx:.1f}, expected {expected_x:.1f}'
    assert abs(rx - (expected_x + args.disparity)) <= 1.5, f'right square at {rx:.1f}, expected {expected_x + args.disparity:.1f}'
    assert abs(ly - ry) <= 0.5, f'vertical disparity {ry - ly:.1f} px'
    assert abs(ly - (args.height / 2 - .5)) <= 1.5, f'square height {ly:.1f}'
    for name, w, h in (('left', lw, lh), ('right', rw, rh)):
        assert abs(w - args.square) <= 2 and abs(h - args.square) <= 2, f'{name} square is {w}x{h}, expected {args.square} (full size)'
    print(f'left square {lx:.1f},{ly:.1f} {lw}x{lh}; right square {rx:.1f},{ry:.1f} {rw}x{rh}; '
          f'disparity {rx - lx:+.1f} px (expected {args.disparity:+d}), vertical {ry - ly:+.1f} px')


if __name__ == '__main__':
    main()
