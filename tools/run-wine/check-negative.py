#!/usr/bin/env python3
"""Regression cases: the parallax oracle must reject these broken frames."""
import sys
import numpy as np
from check import check, read_xwd

frame = read_xwd(sys.argv[1])
for name, invalid in [('black', np.zeros_like(frame)),
                      ('one black eye', np.concatenate([frame[:, :400], np.zeros_like(frame[:, :400])], 1)),
                      ('identical eyes', np.concatenate([frame[:, :400], frame[:, :400]], 1)),
                      ('reversed eyes', np.concatenate([frame[:, 400:], frame[:, :400]], 1))]:
    try:
        check(invalid, 'half', .16)
    except AssertionError:
        print('PASS: rejected', name)
    else:
        raise SystemExit('FAIL: accepted ' + name)
try:
    check(frame, 'half', .08)
except AssertionError:
    print('PASS: rejected wrong separation')
else:
    raise SystemExit('FAIL: accepted wrong separation')
