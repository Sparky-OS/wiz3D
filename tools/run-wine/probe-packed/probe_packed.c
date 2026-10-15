// A Direct3D 9 program that draws a stereo pair the way games with a 3D mode of
// their own draw it, packed into one back buffer: side by side or top and bottom
// at half size, rows, columns, a checkerboard, alternate frames, or an anaglyph.
// The two eyes are made on the CPU, so every packed pixel is known: the left eye
// is a red field with a white square, the right eye a blue field with the same
// square moved right by PROBE_DISPARITY pixels (grey fields for the anaglyphs).
// DXVK's stereo input (dxvk.stereoInput) has to turn the packed picture into full
// side by side, left eye first; the check script measures the result.
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned WIDTH = 800;
static unsigned HEIGHT = 600;
static unsigned SQUARE = 40;
static int DISPARITY = 32;

typedef struct { float x, y, z, rhw; float u, v; } VERT;
#define FVF (D3DFVF_XYZRHW | D3DFVF_TEX1)

enum packing { SIDE_BY_SIDE, TOP_AND_BOTTOM, ROWS, COLUMNS, CHECKERBOARD, FRAME_SEQUENTIAL,
               ANAGLYPH_RED_CYAN, ANAGLYPH_GREEN_MAGENTA, ANAGLYPH_AMBER_BLUE, NONE };

static const char *names[] = { "sideBySide", "topAndBottom", "rows", "columns", "checkerboard",
                               "frameSequential", "anaglyphRedCyan", "anaglyphGreenMagenta",
                               "anaglyphAmberBlue", "none" };

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

// One eye's pixel: the field, or the white square centred at (cx, HEIGHT/2).
static DWORD eye_pixel(int eye, unsigned x, unsigned y, int grey)
{
    int cx = (int)(WIDTH * 3 / 10) + (eye ? DISPARITY : 0);
    int cy = (int)HEIGHT / 2;
    int inside = (int)x >= cx - (int)SQUARE / 2 && (int)x < cx + (int)SQUARE / 2 &&
                 (int)y >= cy - (int)SQUARE / 2 && (int)y < cy + (int)SQUARE / 2;
    if (inside) return 0xffffffff;
    if (grey) return eye ? 0xff505050 : 0xff303030;
    return eye ? 0xff0000c8 : 0xffc80000;
}

static int luma(DWORD c) { return (int)(((c >> 16) & 0xff) * 0.2126 + ((c >> 8) & 0xff) * 0.7152 + (c & 0xff) * 0.0722); }

// The packed picture of WIDTH x HEIGHT pixels; `first` is the eye that takes the
// first place of the packing (0 the left eye, 1 the right eye); for alternate
// frames `frame` picks the eye of this frame.
static void pack(DWORD *out, enum packing packing, int first, int frame)
{
    for (unsigned y = 0; y < HEIGHT; y++)
        for (unsigned x = 0; x < WIDTH; x++) {
            int eye, sx = (int)x, sy = (int)y;
            DWORD p;
            switch (packing) {
            case SIDE_BY_SIDE:
                eye = (x < WIDTH / 2) ? first : !first;
                sx = (int)((x % (WIDTH / 2)) * 2);
                p = eye_pixel(eye, sx, sy, 0);
                break;
            case TOP_AND_BOTTOM:
                eye = (y < HEIGHT / 2) ? first : !first;
                sy = (int)((y % (HEIGHT / 2)) * 2);
                p = eye_pixel(eye, sx, sy, 0);
                break;
            case ROWS:
                eye = (y & 1) ? !first : first;
                p = eye_pixel(eye, sx, sy, 0);
                break;
            case COLUMNS:
                eye = (x & 1) ? !first : first;
                p = eye_pixel(eye, sx, sy, 0);
                break;
            case CHECKERBOARD:
                eye = ((x + y) & 1) ? !first : first;
                p = eye_pixel(eye, sx, sy, 0);
                break;
            case FRAME_SEQUENTIAL:
                eye = (frame & 1) ? !first : first;
                p = eye_pixel(eye, sx, sy, 0);
                break;
            case ANAGLYPH_RED_CYAN: {
                int l = luma(eye_pixel(first, sx, sy, 1)), r = luma(eye_pixel(!first, sx, sy, 1));
                p = 0xff000000 | (l << 16) | (r << 8) | r;
                break;
            }
            case ANAGLYPH_GREEN_MAGENTA: {
                int l = luma(eye_pixel(first, sx, sy, 1)), r = luma(eye_pixel(!first, sx, sy, 1));
                p = 0xff000000 | (r << 16) | (l << 8) | r;
                break;
            }
            case ANAGLYPH_AMBER_BLUE: {
                int l = luma(eye_pixel(first, sx, sy, 1)), r = luma(eye_pixel(!first, sx, sy, 1));
                p = 0xff000000 | (l << 16) | (l << 8) | r;
                break;
            }
            default:
                p = eye_pixel(0, sx, sy, 0);
            }
            out[y * WIDTH + x] = p;
        }
}

static IDirect3DTexture9 *make_texture(DWORD *pixels)
{
    IDirect3DTexture9 *tex = NULL;
    HRESULT hr = dev->lpVtbl->CreateTexture(dev, WIDTH, HEIGHT, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &tex, NULL);
    checkhr(hr, "CreateTexture");
    if (FAILED(hr)) return NULL;
    D3DLOCKED_RECT lr;
    hr = tex->lpVtbl->LockRect(tex, 0, &lr, NULL, 0);
    checkhr(hr, "LockRect");
    if (SUCCEEDED(hr)) {
        for (unsigned y = 0; y < HEIGHT; y++)
            memcpy((char *)lr.pBits + y * lr.Pitch, pixels + y * WIDTH, WIDTH * 4);
        tex->lpVtbl->UnlockRect(tex, 0);
    }
    return tex;
}

static void render(IDirect3DTexture9 *tex)
{
    // Texel centres on pixel centres: the -0.5 of Direct3D 9's pixel mapping.
    float w = (float)WIDTH, h = (float)HEIGHT;
    VERT v[4] = {
        { -0.5f,     -0.5f,     0.0f, 1.0f, 0.0f, 0.0f },
        { w - 0.5f,  -0.5f,     0.0f, 1.0f, 1.0f, 0.0f },
        { w - 0.5f,  h - 0.5f,  0.0f, 1.0f, 1.0f, 1.0f },
        { -0.5f,     h - 0.5f,  0.0f, 1.0f, 0.0f, 1.0f },
    };
    dev->lpVtbl->Clear(dev, 0, NULL, D3DCLEAR_TARGET, D3DCOLOR_XRGB(0, 0, 0), 1.0f, 0);
    checkhr(dev->lpVtbl->BeginScene(dev), "BeginScene");
    dev->lpVtbl->SetTexture(dev, 0, (IDirect3DBaseTexture9 *)tex);
    checkhr(dev->lpVtbl->DrawPrimitiveUP(dev, D3DPT_TRIANGLEFAN, 2, v, sizeof(VERT)), "DrawPrimitiveUP");
    checkhr(dev->lpVtbl->EndScene(dev), "EndScene");
    checkhr(dev->lpVtbl->Present(dev, NULL, NULL, NULL, NULL), "Present");
}

int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmd, int show)
{
    (void)prev; (void)cmd; (void)show;
    enum packing packing = NONE;
    const char *name = getenv("PROBE_PACKING") ? getenv("PROBE_PACKING") : "none";
    for (unsigned i = 0; i < sizeof(names) / sizeof(*names); i++)
        if (!strcmp(name, names[i])) packing = (enum packing)i;
    if (!strcmp(name, "sideBySideQuincunx")) packing = SIDE_BY_SIDE;
    if (packing == NONE && strcmp(name, "none")) { printf("PROBE FAIL: unknown packing %s\n", name); return 6; }
    int first = getenv("PROBE_RIGHT_FIRST") ? 1 : 0;
    if (getenv("PROBE_DISPARITY")) DISPARITY = atoi(getenv("PROBE_DISPARITY"));

    WNDCLASSA wc = { 0 };
    wc.lpfnWndProc = DefWindowProcA;
    wc.hInstance = inst;
    wc.lpszClassName = "wiz3dpacked";
    RegisterClassA(&wc);
    hwnd = CreateWindowExA(0, "wiz3dpacked", "wiz3dpacked-x", WS_POPUP, 100, 50, WIDTH, HEIGHT, NULL, NULL, inst, NULL);
    ShowWindow(hwnd, SW_SHOW);

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
    pp.PresentationInterval = D3DPRESENT_INTERVAL_IMMEDIATE;
    HRESULT hr = d3d->lpVtbl->CreateDevice(d3d, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd,
                                           D3DCREATE_HARDWARE_VERTEXPROCESSING, &pp, &dev);
    if (FAILED(hr)) { printf("PROBE FAIL: CreateDevice 0x%08lx\n", hr); return 3; }
    dev->lpVtbl->SetRenderState(dev, D3DRS_LIGHTING, FALSE);
    dev->lpVtbl->SetRenderState(dev, D3DRS_CULLMODE, D3DCULL_NONE);
    dev->lpVtbl->SetSamplerState(dev, 0, D3DSAMP_MINFILTER, D3DTEXF_POINT);
    dev->lpVtbl->SetSamplerState(dev, 0, D3DSAMP_MAGFILTER, D3DTEXF_POINT);
    dev->lpVtbl->SetTextureStageState(dev, 0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
    dev->lpVtbl->SetTextureStageState(dev, 0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
    dev->lpVtbl->SetFVF(dev, FVF);

    DWORD *pixels = malloc(WIDTH * HEIGHT * 4);
    pack(pixels, packing, first, 0);
    IDirect3DTexture9 *tex[2] = { make_texture(pixels), NULL };
    if (packing == FRAME_SEQUENTIAL) {
        pack(pixels, packing, first, 1);
        tex[1] = make_texture(pixels);
    }
    free(pixels);
    printf("PROBE: device created, packing %s, %s eye first, square %u px, disparity %d px\n",
           name, first ? "right" : "left", SQUARE, DISPARITY);
    fflush(stdout);

    unsigned frames = 0;
    DWORD start = GetTickCount();
    char stopfile[MAX_PATH];
    GetCurrentDirectoryA(MAX_PATH, stopfile);
    lstrcatA(stopfile, "\\stop.flag");
    while (GetTickCount() - start < 120000) {
        MSG msg;
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE))
            DispatchMessageA(&msg);
        if (GetFileAttributesA(stopfile) != INVALID_FILE_ATTRIBUTES) break;
        render(tex[1] && (frames & 1) ? tex[1] : tex[0]);
        if (err_reported) break;
        if (++frames == 20) { printf("PROBE: ready\n"); fflush(stdout); }
        Sleep(6);
    }
    printf("PROBE: %u frames\n", frames);
    fflush(stdout);
    return err_reported ? 5 : 0;
}
