// wiz3D milestone 3 probe: minimal D3D9 program that renders three marker
// quads at known view depths with a known identity-view perspective camera,
// so that the stereo parallax induced by the wrapper can be predicted
// analytically and checked against the presented frame.
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned WIDTH = 800;
static unsigned HEIGHT = 600;

typedef struct { float x, y, z; DWORD color; } VERT;
#define FVF (D3DFVF_XYZ | D3DFVF_DIFFUSE)

static IDirect3DDevice9 *dev;
static HWND hwnd;
static int err_reported;

static void checkhr(HRESULT hr, const char *what)
{
    if (FAILED(hr) && !err_reported) {
        err_reported = 1;
        printf("PROBE FAIL: %s returned 0x%08lx\n", what, (unsigned long)hr);
        fflush(stdout);
    }
}

static void quad(float cx, float z, float hw, DWORD color)
{
    VERT v[4] = {
        { cx - hw, +hw, z, color },
        { cx + hw, +hw, z, color },
        { cx + hw, -hw, z, color },
        { cx - hw, -hw, z, color },
    };
    checkhr(dev->lpVtbl->DrawPrimitiveUP(dev, D3DPT_TRIANGLEFAN, 2, v, sizeof(VERT)),
            "DrawPrimitiveUP");
}

// Dump the presented back buffer to a binary PPM via readback, so the test
// does not depend on the X11 presentation path being captured correctly.
static void dump_backbuffer(const char *path)
{
    IDirect3DSurface9 *bb = NULL, *sys = NULL;
    HRESULT hr = dev->lpVtbl->GetBackBuffer(dev, 0, 0, D3DBACKBUFFER_TYPE_MONO, &bb);
    checkhr(hr, "GetBackBuffer");
    if (FAILED(hr)) return;
    D3DSURFACE_DESC desc;
    bb->lpVtbl->GetDesc(bb, &desc);
    printf("PROBE: backbuffer %lux%lu format %lu pool %lu\n",
           (unsigned long)desc.Width, (unsigned long)desc.Height,
           (unsigned long)desc.Format, (unsigned long)desc.Pool);
    fflush(stdout);
    hr = dev->lpVtbl->CreateOffscreenPlainSurface(dev, desc.Width, desc.Height,
                                                  desc.Format, D3DPOOL_SYSTEMMEM, &sys, NULL);
    checkhr(hr, "CreateOffscreenPlainSurface");
    if (SUCCEEDED(hr))
        hr = dev->lpVtbl->GetRenderTargetData(dev, bb, sys);
    checkhr(hr, "GetRenderTargetData");
    if (SUCCEEDED(hr)) {
        D3DLOCKED_RECT lr;
        hr = sys->lpVtbl->LockRect(sys, &lr, NULL, D3DLOCK_READONLY);
        checkhr(hr, "LockRect");
        if (SUCCEEDED(hr)) {
            FILE *f = fopen(path, "wb");
            if (f) {
                fprintf(f, "P6\n%lu %lu\n255\n",
                        (unsigned long)desc.Width, (unsigned long)desc.Height);
                const unsigned char *row = lr.pBits;
                for (unsigned y = 0; y < desc.Height; y++, row += lr.Pitch)
                    for (unsigned x = 0; x < desc.Width; x++) {
                        unsigned char b = row[x * 4 + 0], g = row[x * 4 + 1],
                                      r = row[x * 4 + 2];
                        fputc(r, f); fputc(g, f); fputc(b, f);
                    }
                fclose(f);
                printf("PROBE: dumped backbuffer to %s\n", path);
                fflush(stdout);
            }
            sys->lpVtbl->UnlockRect(sys);
        }
    }
    if (sys) sys->lpVtbl->Release(sys);
    bb->lpVtbl->Release(bb);
}

static void render(void)
{
    D3DMATRIX ident = { .m = {{1,0,0,0}, {0,1,0,0}, {0,0,1,0}, {0,0,0,1}} };
    // Perspective LH, fov 90 deg, aspect 1, zn 1, zf 1000:
    // _11 = 1, _22 = 1, _33 = zf/(zf-zn), _34 = 1, _43 = -zn*_33.
    float m33 = 1000.0f / 999.0f;
    D3DMATRIX proj = { .m = {{1,0,0,0}, {0,1,0,0}, {0,0,m33,1}, {0,0,-m33,0}} };
    dev->lpVtbl->SetTransform(dev, D3DTS_VIEW, &ident);
    dev->lpVtbl->SetTransform(dev, D3DTS_WORLD, &ident);
    dev->lpVtbl->SetTransform(dev, D3DTS_PROJECTION, &proj);
    dev->lpVtbl->Clear(dev, 0, NULL, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER,
                       D3DCOLOR_XRGB(0, 0, 0), 1.0f, 0);
    checkhr(dev->lpVtbl->BeginScene(dev), "BeginScene");
    // red: z=4, mono NDC x = -0.6/4 = -0.15
    quad(-0.6f, 4.0f, 0.1f, D3DCOLOR_XRGB(255, 40, 40));
    // green: z=1000, mono NDC x = -0.03
    quad(-30.0f, 1000.0f, 25.0f, D3DCOLOR_XRGB(40, 255, 40));
    // blue: z=2, mono NDC x = 0.25
    quad(0.5f, 2.0f, 0.05f, D3DCOLOR_XRGB(40, 40, 255));
    checkhr(dev->lpVtbl->EndScene(dev), "EndScene");
    checkhr(dev->lpVtbl->Present(dev, NULL, NULL, NULL, NULL), "Present");
}

int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmd, int show)
{
    (void)prev; (void)cmd; (void)show;
    if (getenv("PROBE_WIDTH")) WIDTH = strtoul(getenv("PROBE_WIDTH"), NULL, 10);
    if (getenv("PROBE_HEIGHT")) HEIGHT = strtoul(getenv("PROBE_HEIGHT"), NULL, 10);
    if (!WIDTH || !HEIGHT || WIDTH > 1600 || HEIGHT > 1000) return 6;
    WNDCLASSA wc = { 0 };
    wc.lpfnWndProc = DefWindowProcA;
    wc.hInstance = inst;
    wc.lpszClassName = "wiz3dprobe";
    RegisterClassA(&wc);
    hwnd = CreateWindowExA(0, "wiz3dprobe", "wiz3dprobe-x", WS_POPUP,
                           100, 50, WIDTH, HEIGHT, NULL, NULL, inst, NULL);
    ShowWindow(hwnd, SW_SHOW);

    // Early test for milestone 4: does Wine mirror __wine_x11_ props to X11?
    if (!SetPropA(hwnd, "__wine_x11_WIZ3D_TEST", (HANDLE)(ULONG_PTR)0xC0DE) ||
        GetPropA(hwnd, "__wine_x11_WIZ3D_TEST") != (HANDLE)(ULONG_PTR)0xC0DE)
        return 4;
    printf("PROBE: Win32 test property verified; pid=%lu xid=%p\n", GetCurrentProcessId(), GetPropA(hwnd, "__wine_x11_whole_window"));

    IDirect3D9 *d3d = Direct3DCreate9(D3D_SDK_VERSION);
    if (!d3d) { printf("PROBE FAIL: Direct3DCreate9\n"); return 2; }
    D3DPRESENT_PARAMETERS pp = { 0 };
    pp.BackBufferWidth = WIDTH;
    pp.BackBufferHeight = HEIGHT;
    pp.BackBufferFormat = D3DFMT_X8R8G8B8;
    pp.BackBufferCount = 1;
    pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
    pp.hDeviceWindow = hwnd;
    pp.Windowed = getenv("PROBE_FULLSCREEN") ? FALSE : TRUE;
    pp.EnableAutoDepthStencil = TRUE;
    pp.AutoDepthStencilFormat = D3DFMT_D16;
    pp.PresentationInterval = D3DPRESENT_INTERVAL_IMMEDIATE;
    HRESULT hr = d3d->lpVtbl->CreateDevice(d3d, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL,
                                           hwnd, D3DCREATE_HARDWARE_VERTEXPROCESSING,
                                           &pp, &dev);
    if (FAILED(hr)) { printf("PROBE FAIL: CreateDevice 0x%08lx\n", hr); return 3; }
    if (getenv("PROBE_FULL_MODE")) {
        typedef void *(CALLBACK *CreateOutput)(DWORD, DWORD);
        HMODULE output = GetModuleHandleA("SideBySideOutput.dll");
        CreateOutput create = (CreateOutput)(void *)GetProcAddress(output, "CreateOutputDX10");
        if (!create || create(3, 0) != NULL) {
            printf("PROBE FAIL: DX9-only mode accepted by DX10 output\n");
            return 7;
        }
        printf("PROBE: DX10 correctly rejects the DX9-only mode\n");
    }
    dev->lpVtbl->SetRenderState(dev, D3DRS_LIGHTING, FALSE);
    dev->lpVtbl->SetRenderState(dev, D3DRS_CULLMODE, D3DCULL_NONE);
    dev->lpVtbl->SetFVF(dev, FVF);
    printf("PROBE: device created\n");
    fflush(stdout);

    unsigned frames = 0;
    DWORD start = GetTickCount();
    char stopfile[MAX_PATH];
    GetCurrentDirectoryA(MAX_PATH, stopfile);
    lstrcatA(stopfile, "\\stop.flag");
    char dumpfile[MAX_PATH];
    lstrcpyA(dumpfile, stopfile);
    // reuse CWD: dump.flag -> write frame-bb.ppm
    {
        char *p = strrchr(dumpfile, '\\');
        if (p) p[1] = 0;
        lstrcatA(dumpfile, "dump.flag");
    }
    while (GetTickCount() - start < 120000) {
        MSG msg;
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE))
            DispatchMessageA(&msg);
        DWORD attr = GetFileAttributesA(stopfile);
        if (attr != INVALID_FILE_ATTRIBUTES) break;
        render();
        if (err_reported) break;
        if (++frames == 10 && getenv("PROBE_RESET")) {
            pp.BackBufferWidth = (getenv("PROBE_RESET_AUTO") || getenv("PROBE_RESET_WIDTH_ONLY")) ? 0 : WIDTH;
            pp.BackBufferHeight = getenv("PROBE_RESET_AUTO") ? 0 : HEIGHT;
            checkhr(dev->lpVtbl->Reset(dev, &pp), "Reset");
            dev->lpVtbl->SetRenderState(dev, D3DRS_LIGHTING, FALSE);
            dev->lpVtbl->SetRenderState(dev, D3DRS_CULLMODE, D3DCULL_NONE);
            dev->lpVtbl->SetFVF(dev, FVF);
            printf("PROBE: reset completed\n");
        }
        if (frames == 20) { printf("PROBE: ready\n"); fflush(stdout); }
        if (GetFileAttributesA(dumpfile) != INVALID_FILE_ATTRIBUTES) {
            dump_backbuffer("frame-bb.ppm");
            DeleteFileA(dumpfile);
        }
        Sleep(6);
    }
    printf("PROBE: exiting\n");
    dev->lpVtbl->Release(dev);
    d3d->lpVtbl->Release(d3d);
    DestroyWindow(hwnd);
    return err_reported ? 5 : 0;
}
