#!/usr/bin/env python3
"""Generate a ninja build for the wiz3D DX9 path (Release|Win32) on Linux.

Reads the vcxproj files of the DX9 chain (proxy, S3DAPI, and their static-lib
dependencies plus the SideBySide output plugin) and emits build.ninja targeted
at clang-cl + lld-link with an xwin-splatted Windows SDK/CRT.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xml.etree import ElementTree as ET

NS = {'m': 'http://schemas.microsoft.com/developer/msbuild/2003'}
CONFIG = 'Release'
ARCH = os.environ.get('WIZ3D_ARCH', 'x64')   # x64 or x86
PLATFORM = {'x64': 'x64', 'x86': 'Win32'}[ARCH]
A86 = 'x64' if ARCH == 'x64' else 'x86'      # vendor lib folder spelling
A32 = 'x64' if ARCH == 'x64' else 'x32'      # MinHook spelling
XA = 'x86_64' if ARCH == 'x64' else 'x86'    # xwin folder spelling
COND = f"'$(Configuration)|$(Platform)'=='{CONFIG}|{PLATFORM}'"
PLATCOND = f"'$(Platform)'=='{PLATFORM}'"

# Lib-name macros from ThirdPartyLibs/ThirdPartyLibs.props (Release, x86).
LIBMACROS = {
    'MinHookLib': f'minhook.{A32}.lib',
    'SRLib': 'SR-mt.lib',
    'ZlibLib': 'zs.lib',
    'XercesLib': 'xerces-c_3.lib',
    'SquishLib': 'squish.lib',
    'DevILLib': 'DevIL.lib',
    'ILULib': 'ILU.lib',
    'LibPngLib': 'libpng16.lib',
    'JpegLib': 'jpeg.lib',
    'D3DX9Lib': 'd3dx9.lib',
    'D3DX10Lib': 'd3dx10.lib',
    'D3DX11Lib': 'd3dx11.lib',
    'DxErrLib': 'DxErr.lib',
}

# System default libs (Microsoft.Cpp.Common.props CoreLibraryDependencies).
SYSTEM_LIBS = ['kernel32.lib', 'user32.lib', 'gdi32.lib', 'winspool.lib',
               'comdlg32.lib', 'advapi32.lib', 'shell32.lib', 'ole32.lib',
               'oleaut32.lib', 'uuid.lib', 'odbc32.lib', 'odbccp32.lib',
               'legacy_stdio_definitions.lib', 'ticpp.lib',
               'comctl32.lib', 'shlwapi.lib', 'rpcrt4.lib']

# Include dirs every project gets: Common.props, ThirdPartyLibs.props,
# LlamaXML_shim.props.
TARGET = '--target=x86_64-pc-windows-msvc' if ARCH == 'x64' else '--target=i686-pc-windows-msvc'

def common_includes(sol):
    t = os.path.join(sol, 'ThirdPartyLibs')
    return [sol, os.path.join(sol, 'Shared')] + [
        os.path.join(t, p) for p in (
            'MinHook_v1.3.4/include',
            'SR-Lib_v2.0.0/include',
            'zlib_v1.3.2/Include',
            'xerces-c_v3.3.0/Include',
            'libsquish_v1.15/Include',
            'DevIL_v1.8.0/Include',
            'DirectXSDK_Jun2010/Include',
            'boost_v1.91.0/Include',
        )] + [os.path.join(sol, 'lib/ticpp_2.5.3/Include'),
              os.path.join(sol, 'lib/LlamaXML')]

def common_libdirs(sol):
    t = os.path.join(sol, 'ThirdPartyLibs')
    return [os.path.join(t, p, f'lib/{A86}/Release') for p in (
        'MinHook_v1.3.4', 'SR-Lib_v2.0.0', 'zlib_v1.3.2', 'xerces-c_v3.3.0',
        'libsquish_v1.15', 'DevIL_v1.8.0', 'DirectXSDK_Jun2010')] + [
        os.path.join(sol, f'lib/ticpp_2.5.3/Lib/{A86}/Release'),
        os.path.join(sol, 'ThirdPartyLibs/boost_v1.91.0/lib')]

# Global defines: Release.props + Common.props + Directory.Build.props +
# LlamaXML_shim.props.
GLOBAL_DEFINES = ('IZ3D_BUILD;_HAS_EXCEPTIONS=0;BOOST_NO_STD_TYPEINFO;'
                  '_HAS_ITERATOR_DEBUGGING=0;'
                  '_SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS;STRSAFE_NO_DEPRECATE;'
                  'IL_STATIC_LIB;BOOST_ALL_NO_LIB;TIXML_USE_TICPP;'
                  'UNICODE;_UNICODE')

def normpath(sol, base, p):
    """Case-insensitively resolve a backslashed MSBuild path against the FS."""
    p = p.replace('\\', '/').replace('$(SolutionDir)', sol + '/')
    if not os.path.isabs(p):
        p = os.path.normpath(os.path.join(base, p))
    else:
        p = os.path.normpath(p)
    if os.path.exists(p):
        return p
    # resolve case-insensitively, component by component
    parts = p.split('/')
    cur = '/'
    out = []
    for part in parts:
        if not part:
            continue
        cand = os.path.join(cur, part)
        if os.path.exists(cand):
            out.append(part)
            cur = cand
            continue
        try:
            entries = os.listdir(cur)
        except OSError:
            return p  # give up, return as-is
        match = next((e for e in entries if e.lower() == part.lower()), None)
        if match is None:
            return p
        out.append(match)
        cur = os.path.join(cur, match)
    return '/' + '/'.join(out)

def expand_libs(s):
    for k, v in LIBMACROS.items():
        s = s.replace(f'$({k})', v)
    return s

_CTX = {}

def strip_macros(s):
    s = s.replace('$(SolutionDir)', _CTX['sol'] + '/').replace('$(ProjectDir)', _CTX.get('dir', '.') + '/')
    s = re.sub(r'%\([^)]*\)', '', s)
    s = re.sub(r'\$\((OutDir|IntDir|TargetName|ProjectDir|MSBuildThisFileDirectory|SolutionDir|_TPL|_LIB|_Arch86|_Arch32|_Config)\)', '', s)
    s = re.sub(r'\$\((\w+)\)', r'\1', s)
    return s

class Project:
    def __init__(self, sol, relpath):
        self.sol = sol
        self.relpath = relpath.replace('\\', '/')
        self.dir = os.path.dirname(os.path.join(sol, self.relpath))
        _CTX['sol'], _CTX['dir'] = sol, self.dir
        t = ET.parse(os.path.join(sol, self.relpath))
        r = t.getroot()
        self.name = os.path.splitext(self.relpath)[0].replace('/', '_')
        for g in r.findall('m:PropertyGroup', ns := NS):
            if g.get('Condition') == COND:
                ct = g.find('m:ConfigurationType', NS)
                if ct is not None:
                    self.ctype = ct.text
        if not hasattr(self, 'ctype'):
            self.ctype = 'StaticLibrary'
        pn = r.find('m:PropertyGroup/m:ProjectName', NS)
        self.target = pn.text if pn is not None else os.path.splitext(os.path.basename(self.relpath))[0]
        for g in r.findall('m:PropertyGroup', NS):
            if g.get('Condition') in (None, COND):
                tn = g.find('m:TargetName', NS)
                if tn is not None and tn.text and '$(' not in tn.text:
                    self.target = tn.text
        self.defines = []
        self.includes = []
        self.libs = []
        self.def_file = None
        self.delayloads = []
        self.refs = []
        self.srcs = []
        self.rcs = []
        self.scan(r, sol, set())
        for pr in r.findall('.//m:ProjectReference', NS):
            if pr.get('Include'):
                self.refs.append(pr.get('Include').replace('\\', '/'))
        for cc in r.findall('.//m:ClCompile', NS):
            inc = cc.get('Include')
            if inc is None:
                continue
            excl = cc.find(f"m:ExcludedFromBuild[@Condition=\"{COND}\"]", NS)
            if excl is not None and excl.text == 'true':
                continue
            self.srcs.append(normpath(sol, self.dir, inc))
        for rc in r.findall('.//m:ResourceCompile', NS):
            self.rcs.append(normpath(sol, self.dir, rc.get('Include')))

    def scan(self, r, sol, seen, base=None):
        base = base or self.dir
        # property sheets (<Import>) first: their settings come before the project's
        for g in r.findall('m:ImportGroup', NS):
            if g.get('Condition') not in (None, COND):
                continue
            for im in g.findall('m:Import', NS):
                pj = im.get('Project').replace('\\', '/')
                if '$(' in pj:
                    continue
                path = normpath(sol, base, pj)
                if path in seen or not os.path.isfile(path):
                    continue
                seen.add(path)
                self.scan(ET.parse(path).getroot(), sol, seen, os.path.dirname(path))
        for ig in r.findall('m:ItemDefinitionGroup', NS):
            if ig.get('Condition') not in (None, COND, PLATCOND):
                continue
            cl = ig.find('m:ClCompile', NS)
            if cl is not None:
                d = cl.find('m:PreprocessorDefinitions', NS)
                if d is not None and d.text:
                    self.defines += strip_macros(d.text).split(';')
                i = cl.find('m:AdditionalIncludeDirectories', NS)
                if i is not None and i.text:
                    self.includes += [normpath(sol, self.dir, x) for x in
                                      strip_macros(i.text).split(';') if x.strip()]
            lk = ig.find('m:Link', NS)
            if lk is not None:
                a = lk.find('m:AdditionalDependencies', NS)
                if a is not None and a.text:
                    self.libs += [x for x in strip_macros(expand_libs(a.text)).split(';')
                                  if x.strip()]
                m = lk.find('m:ModuleDefinitionFile', NS)
                if m is not None and m.text:
                    df = strip_macros(m.text.replace('$(ProjectName)', self.target))
                    self.def_file = normpath(sol, self.dir, df)
                dl = lk.find('m:DelayLoadDLLs', NS)
                if dl is not None and dl.text:
                    self.delayloads += [x for x in strip_macros(dl.text).split(';')
                                        if x.strip()]



def find_lib(name, sol, syslib):
    """Link-line names are case-insensitive on Windows; resolve on disk."""
    for d in common_libdirs(sol) + syslib:
        try:
            for e in os.listdir(d):
                if e.lower() == name.lower():
                    return e
        except OSError:
            pass
    return name


def is_utf16(path):
    with open(path, 'rb') as f:
        return f.read(2) in (b'\xff\xfe', b'\xfe\xff')


def main():
    sol = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
    out = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else 'build-linux-out')
    xwin = os.environ.get('XWIN_DIR', '/opt/xwin')
    seeds = ['wiz3D-proxy/d3d9/wiz3D-proxy-d3d9.vcxproj',
             'S3DWrapper9/S3DWrapper9.vcxproj',
             'OutputMethods/SideBySideOutput/SideBySideOutput.vcxproj']
    order, seen = [], set()
    def add(rel):
        rel = os.path.normpath(rel).replace('\\', '/')
        if rel in seen:
            return
        seen.add(rel)
        p = Project(sol, rel)
        base = os.path.dirname(rel)
        for r in p.refs:
            add(os.path.normpath(os.path.join(base, r)))
        order.append(p)
    for s in seeds:
        add(s)
    # Preparing has no sources (Application, content-only); drop it.
    order = [p for p in order if p.srcs or p.ctype != 'Application']
    os.makedirs(out, exist_ok=True)
    def sdk_dir(kind):
        # xwin can lay the SDK out flat, with <SDK version> -> . beside it: use the folder itself, which the VFS overlay covers
        top = f'{xwin}/sdk/{kind}'
        versioned = f'{top}/10.0.26100'
        return top if os.path.islink(versioned) and os.path.realpath(versioned) == os.path.realpath(top) else versioned
    sdkinc = sdk_dir('include')
    sdklib = sdk_dir('lib')
    sysinc = [f'{xwin}/crt/include', f'{sdkinc}/ucrt', f'{sdkinc}/um',
              f'{sdkinc}/shared', f'{sdkinc}/winrt']
    syslib = [f'{xwin}/crt/lib/{XA}', f'{sdklib}/um/{XA}',
              f'{sdklib}/ucrt/{XA}']
    vfs = os.path.join(out, 'vfs.json')
    lines = []
    w = lines.append
    w('rule cc')
    w('  command = clang-cl @${out}.rsp /clang:-MD /clang:-MF /clang:${out}.d /Fo${out} ${in}')
    w('  depfile = ${out}.d')
    w('  deps = gcc')
    w('  rspfile = ${out}.rsp')
    w('  rspfile_content = ${flags}')
    w('  description = CC ${in}')
    w('rule u8')
    w("  command = python3 -c \"import sys;open(sys.argv[2],'w',encoding='utf-8').write(open(sys.argv[1],encoding='utf-16').read())\" ${in} ${out}")
    w('  description = UTF8 ${in}')
    w('rule rcpp')
    w('  command = clang-cl --target=${target} /E /TC /DRC_INVOKED /DUNICODE ${ppflags} ${in} | python3 ${filter} > ${out}')
    w('  description = RCPP ${in}')
    w('rule rc')
    w('  command = llvm-rc /nologo /no-preprocess /C 1252 /fo${out} ${flags} ${in}')
    w('  description = RC ${in}')
    w('rule ar')
    w('  command = llvm-lib /nologo /OUT:${out} ${in}')
    w('  description = AR ${out}')
    w('rule dll')
    w('  command = lld-link ${ldflags} ${in} /OUT:${dllout}')
    w('  description = LINK ${out}')
    objs = {}
    artefact = {}
    linklib = {}
    for p in order:
        pdir = os.path.join(out, 'obj', p.name)
        incflags = f'-Xclang -ivfsoverlay -Xclang {vfs} '
        incflags += ' '.join(f'/imsvc"{d}"' for d in sysinc)
        incflags += ' ' + ' '.join(f'-I"{d}"' for d in
                                   [p.dir, os.path.join(out, 'ver', 'inc')] +
                                   common_includes(sol) + p.includes)
        defflags = ' '.join(f'-D{d}' for d in [GLOBAL_DEFINES.replace(';', ' -D')] + p.defines if d)
        baseflags = (f'/c /nologo /O2 /Oi /Ot /GF /GS- /Gy /fp:fast /MT /EHsc /W3 -msse4.2 '
                     f'/wd4127 /wd4201 /wd4203 /wd4342 /wd4347 /wd4514 '
                     f'/wd4710 /wd4820 /wd4986 /wd4996 -w -ferror-limit=0 -Wno-invalid-token-paste -Wno-c++11-narrowing -Wno-non-pod-varargs '
                     f'{TARGET} {defflags} {incflags}')
        # The wrapper relies on an MSVC behaviour: an `inline` function defined
        # in one TU (ProxyDirect9-inl.h, BaseSwapChain-inl.h) is also called
        # from TUs that only see its declaration. MSVC emits the body; clang
        # drops it once every call in the defining TU is inlined. /Ob0 keeps
        # the bodies, at the cost of inlining, for this project only.
        if p.target == 'S3DWrapperD3D9':
            baseflags += ' /Ob0'
        objs[p.name] = []
        for i, s in enumerate(p.srcs):
            obj = f'{pdir}/{i:03d}_{os.path.basename(s)}.obj'
            objs[p.name].append(obj)
            extra = ''
            if is_utf16(s):
                u8 = f'{pdir}/utf8/{os.path.basename(s)}'
                w(f'build {u8}: u8 {s}')
                extra = f' -I"{os.path.dirname(s)}"'
                w(f'build {obj}: cc {u8}')
            else:
                w(f'build {obj}: cc {s}')
            w(f'  flags = {baseflags}{extra}')
        pobj = os.path.join(out, 'obj')
        for rc in p.rcs:
            res = f'{pdir}/rc_{os.path.basename(rc)}.res'
            objs[p.name].append(res)
            rcpp_inc = ' '.join(f'-I"{d}"' for d in [os.path.dirname(rc), p.dir, os.path.join(sol, 'Shared'), os.path.join(out, 'ver', 'inc')] + p.includes) + ' ' + ' '.join(f'/imsvc"{d}"' for d in sysinc)
            rcincs = ' '.join(f'/i"{d}"' for d in
                              [p.dir, os.path.dirname(rc),
                               os.path.join(sol, 'Shared'),
                               os.path.join(out, 'ver', 'inc')] + sysinc)
            src = rc
            if is_utf16(rc):
                src = f'{pdir}/utf8/{os.path.basename(rc)}'
                w(f'build {src}: u8 {rc}')
            pp = f'{pdir}/rc_{os.path.basename(rc)}.i'
            w(f'build {pp}: rcpp {src}')
            w(f'  target = {TARGET.split("=")[1]}')
            w(f'  filter = {sol}/tools/build-linux/rc_ascii.py')
            w(f'  ppflags = -Xclang -ivfsoverlay -Xclang {vfs} {rcpp_inc} {defflags}')
            w(f'build {res}: rc {pp}')
            w(f'  flags = {rcincs} /DUNICODE')
        if p.ctype == 'StaticLibrary':
            lib = os.path.join(out, 'lib', p.target + '.lib')
            w(f'build {lib}: ar {" ".join(objs[p.name])}')
            artefact[p.name] = lib
        else:
            dll = os.path.join(out, 'bin', p.target + '.dll')
            implib = os.path.join(pdir, p.target + '.imp.lib')
            linklib[p.name] = implib
            syslibs = list(SYSTEM_LIBS)
            reflibs = []
            def deps(q, top=False):
                for r in q.refs:
                    rn = os.path.normpath(os.path.join(os.path.dirname(q.relpath), r)).replace('\\', '/')
                    rname = rn.replace('/', '_').rsplit('.vcxproj', 1)[0]
                    rp = next((x for x in order if x.name == rname), None)
                    if rp is None:
                        continue  # not in the closure (e.g. Preparing)
                    lib = linklib.get(rp.name, artefact[rp.name])
                    if lib not in reflibs:
                        reflibs.append(lib)
                    if rp.ctype == 'StaticLibrary':
                        deps(rp)  # static libs pass their DLL imports on
            deps(p, True)
            ldlibs = reflibs + [find_lib(l, sol, syslib) for l in p.libs if l not in syslibs] + syslibs
            if p.delayloads:
                ldlibs.append('delayimp.lib')
            libpaths = ' '.join(f'/LIBPATH:"{d}"' for d in
                                common_libdirs(sol) + syslib + [os.path.join(out, 'lib')])
            ld = (f'/DLL /NOLOGO /MACHINE:{ARCH.upper()} /SUBSYSTEM:WINDOWS '
                  f'/LARGEADDRESSAWARE /TIMESTAMP:0 /OPT:REF /OPT:ICF /DEBUG:NONE {libpaths} '
                  f'/IMPLIB:"{implib}"')
            if p.def_file:
                ld += f' /DEF:"{p.def_file}"'
            for d in sorted(set(p.delayloads)):
                ld += f' /DELAYLOAD:{d}'
            inp = ' '.join(objs[p.name])
            w(f'build {dll} {implib}: dll {inp} | {" ".join(l for l in reflibs if l.startswith(out))}')
            w(f'  flags = /MT {TARGET}')
            w(f'  dllout = {dll}')
            w(f'  ldflags = {ld} {" ".join(ldlibs)}')
            artefact[p.name] = dll
    allt = ' '.join(artefact[p.name] for p in order)
    w(f'build all: phony {allt}')
    w('default all')
    with open(os.path.join(out, 'build.ninja'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'wrote {out}/build.ninja: {len(order)} projects, '
          f'{sum(len(p.srcs) for p in order)} sources')

if __name__ == '__main__':
    main()
