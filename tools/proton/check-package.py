#!/usr/bin/env python3
"""Assert the staged Linux defaults and the two project licence files."""
from pathlib import Path
import sys
import xml.etree.ElementTree as E

repo, output = map(Path, sys.argv[1:])
for arch in ('x64', 'x86'):
    stage = output / arch
    for name in ('d3d9.dll', 'S3DWrapperD3D9.dll', 'S3DAPI.dll', 'ZLOg.dll',
                 'OutputMethods/SideBySideOutput.dll', 'BaseProfile.xml'):
        assert (stage / name).is_file(), name
    for name in ('LICENSE', 'LICENSE-iZ3D.txt'):
        assert (stage / name).read_bytes() == (repo / name).read_bytes(), name
    root = E.parse(stage / 'wiz3D_Config.xml').getroot()
    value = lambda name: root.find(f'.//{{*}}{name}').get('Value')
    assert value('OutputMethodDll') == 'SideBySideOutput'
    assert value('OutputMode') == '3'
    assert value('SwapEyes') == '0'
    for key in ('ToggleStereo', 'SwapEyes', 'ToggleWizard', 'ToggleHotkeysOSD'):
        assert root.find(f'.//{{*}}Keys/{{*}}{key}').get('Key') == '0', key
    print(f'PASS: {arch} layout, full-SBS defaults, controls, and project licences')
