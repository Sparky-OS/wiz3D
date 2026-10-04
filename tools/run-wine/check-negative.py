#!/usr/bin/env python3
"""Regression cases: the parallax oracle must reject these broken frames."""
import sys
import numpy as np
from check import check, read_xwd

frame = read_xwd(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else 'half'
eye = frame.shape[1] // 2
for name, invalid in [('black', np.zeros_like(frame)),
                      ('one black eye', np.concatenate([frame[:, :eye], np.zeros_like(frame[:, :eye])], 1)),
                      ('identical eyes', np.concatenate([frame[:, :eye], frame[:, :eye]], 1)),
                      ('reversed eyes', np.concatenate([frame[:, eye:], frame[:, :eye]], 1))]:
    try:
        check(invalid, mode, .16, frame.shape[1] // (2 if mode == 'full' else 1), frame.shape[0])
    except AssertionError:
        print('PASS: rejected', name)
    else:
        raise SystemExit('FAIL: accepted ' + name)
try:
    check(frame, mode, .08, frame.shape[1] // (2 if mode == 'full' else 1), frame.shape[0])
except AssertionError:
    print('PASS: rejected wrong separation')
else:
    raise SystemExit('FAIL: accepted wrong separation')
