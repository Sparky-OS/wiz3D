#!/usr/bin/env python3
"""Copy the built DLLs into the runtime layout: proxy and wrapper DLLs next
to each other, output plug-ins in OutputMethods/ (see S3DAPI LoadOutputDll)."""
import os, shutil, sys
import xml.etree.ElementTree as ET
build, out, sol, arch = sys.argv[1:5]
shutil.rmtree(out, ignore_errors=True)
os.makedirs(os.path.join(out, 'OutputMethods'))
for f in sorted(os.listdir(os.path.join(build, 'bin'))):
    dest = 'OutputMethods' if f.lower().startswith('sidebyside') else ''
    shutil.copy(os.path.join(build, 'bin', f), os.path.join(out, dest, f))
    print('staged', os.path.join(dest, f))

# runtime config template shipped with the project's own DX9 release layout
cfg = os.path.join(sol, 'releases', 'wiz3D', 'dx9', arch, 'wiz3D_Config.xml')
if os.path.isfile(cfg):
    ET.register_namespace('', 'http://schemas.iz3d.com/config/2007')
    tree = ET.parse(cfg)
    values = dict(OutputMethodDll='SideBySideOutput', OutputMode='3', OutputSpanMode='0',
                  ShowFPS='0', ShowOSD='0', ShowWizardAtStartup='0', SwapEyes='0')
    for node in tree.iter():
        tag = node.tag.split('}')[-1]
        if 'Value' in node.attrib and tag in values:
            node.set('Value', values[tag])
        if 'Key' in node.attrib and tag in ('ToggleStereo', 'SwapEyes', 'ToggleWizard', 'ToggleHotkeysOSD'):
            node.set('Key', '0')
    tree.write(os.path.join(out, 'wiz3D_Config.xml'), encoding='utf-8', xml_declaration=True)
    print('staged KWin full-SBS configuration')
for license_file in ('LICENSE', 'LICENSE-iZ3D.txt'):
    shutil.copy(os.path.join(sol, license_file), out)
prof = os.path.join(sol, 'S3DDriverSetup', 'Content', 'BaseProfile.xml')
if os.path.isfile(prof):
    shutil.copy(prof, out)
    print('staged BaseProfile.xml')
