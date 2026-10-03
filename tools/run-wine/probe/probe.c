// wiz3D milestone 3 probe: minimal D3D9 program that renders three marker
// quads at known view depths with a known identity-view perspective camera,
// so that the stereo parallax induced by the wrapper can be predicted
// analytically and checked against the presented frame.
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>

#define WIDTH  800
#define HEIGHT 600

typedef struct { float x, y, z; DWORD color; } VERT;
#define FVF (D3DFVF_XYZ | D3DFVF_DIFFUSE)

static IDirect3DDevice9 *dev;
static HWND hwnd;

static void quad(float cx, float z, float hw, DWORD color)
{
    VERT v[4] = {
        { cx - hw, +hw, z, color },
        { cx + hw, +hw, z, color },
        { cx + hw, -hw, z, color },
        { cx - hw, -hw, z, color },
    };
    dev->lpVtbl->DrawPrimitiveUP(dev, D3DPT_TRIANGLEFAN, 2, v, sizeof(VERT));
}

static void render(void)
{
    D3DMATRIX ident = { 1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1 };
    // Perspective LH, fov 90 deg, aspect 1, zn 1, zf 1000:
    // _11 = 1, _22 = 1, _33 = zf/(zf-zn), _34 = 1, _43 = -zn*_33.
    float m33 = 1000.0f / 999.0f;
    D3DMATRIX proj = { 1,0,0,0, 0,1,0,0, 0,0,m33,1, 0,0,-m33,0 };
    dev->lpVtbl->SetTransform(dev, D3DTS_VIEW, &ident);
    dev->lpVtbl->SetTransform(dev, D3DTS_WORLD, &ident);
    dev->lpVtbl->SetTransform(dev, D3DTS_PROJECTION, &proj);
    dev->lpVtbl->Clear(dev, 0, NULL, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER,
                       D3DCOLOR_XRGB(0, 0, 0), 1.0f, 0);
    dev->lpVtbl->BeginScene(dev);
    // red: z=4, mono NDC x = -0.6/4 = -0.15
    quad(-0.6f, 4.0f, 0.1f, D3DCOLOR_XRGB(255, 40, 40));
    // green: z=1000, mono NDC x = -0.03
    quad(-30.0f, 1000.0f, 5.0f, D3DCOLOR_XRGB(40, 255, 40));
    // blue: z=2, mono NDC x = 0.25
    quad(0.5f, 2.0f, 0.05f, D3DCOLOR_XRGB(40, 40, 255));
    dev->lpVtbl->EndScene(dev);
    dev->lpVtbl->Present(dev, NULL, NULL, NULL, NULL);
}

int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmd, int show)
{
    (void)prev; (void)cmd; (void)show;
    WNDCLASSA wc = { 0 };
    wc.lpfnWndProc = DefWindowProcA;
    wc.hInstance = inst;
    wc.lpszClassName = "wiz3dprobe";
    RegisterClassA(&wc);
    hwnd = CreateWindowExA(0, "wiz3dprobe", "wiz3dprobe-x", WS_POPUP,
                           100, 50, WIDTH, HEIGHT, NULL, NULL, inst, NULL);
    ShowWindow(hwnd, SW_SHOW);

    // Early test for milestone 4: does Wine mirror __wine_x11_ props to X11?
    SetPropA(hwnd, "__wine_x11_WIZ3D_TEST", (HANDLE)(ULONG_PTR)0xC0DE);

    IDirect3D9 *d3d = Direct3DCreate9(D3D_SDK_VERSION);
    if (!d3d) { printf("PROBE FAIL: Direct3DCreate9\n"); return 2; }
    D3DPRESENT_PARAMETERS pp = { 0 };
    pp.BackBufferWidth = WIDTH;
    pp.BackBufferHeight = HEIGHT;
    pp.BackBufferFormat = D3DFMT_X8R8G8B8;
    pp.BackBufferCount = 1;
    pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
    pp.hDeviceWindow = hwnd;
    pp.Windowed = TRUE;
    pp.EnableAutoDepthStencil = TRUE;
    pp.AutoDepthStencilFormat = D3DFMT_D16;
    pp.PresentationInterval = D3DPRESENT_INTERVAL_IMMEDIATE;
    HRESULT hr = d3d->lpVtbl->CreateDevice(d3d, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL,
                                           hwnd, D3DCREATE_HARDWARE_VERTEXPROCESSING,
                                           &pp, &dev);
    if (FAILED(hr)) { printf("PROBE FAIL: CreateDevice 0x%08lx\n", hr); return 3; }
    dev->lpVtbl->SetRenderState(dev, D3DRS_LIGHTING, FALSE);
    dev->lpVtbl->SetRenderState(dev, D3DRS_CULLMODE, D3DCULL_NONE);
    printf("PROBE: device created\n");
    fflush(stdout);

    DWORD start = GetTickCount();
    char stopfile[MAX_PATH];
    GetCurrentDirectoryA(MAX_PATH, stopfile);
    lstrcatA(stopfile, "\\stop.flag");
    while (GetTickCount() - start < 120000) {
        MSG msg;
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE))
            DispatchMessageA(&msg);
        DWORD attr = GetFileAttributesA(stopfile);
        if (attr != INVALID_FILE_ATTRIBUTES) break;
        render();
        Sleep(6);
    }
    printf("PROBE: exiting\n");
    return 0;
}
