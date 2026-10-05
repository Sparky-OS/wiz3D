// Quad-buffer stereo OpenGL probe: a PFD_STEREO pixel format, red in GL_BACK_LEFT,
// green in GL_BACK_RIGHT, one view's size window. Usage: glstereo [seconds] [mono]
// With "mono": an ordinary double-buffered format, red drawn to GL_BACK.
#include <windows.h>
#include <GL/gl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    int seconds = argc > 1 ? atoi(argv[1]) : 20, i, count, format = 0;
    int mono = argc > 2 && !strcmp(argv[2], "mono");
    PIXELFORMATDESCRIPTOR pfd;
    WNDCLASSA wc = { 0 };
    HWND hwnd;
    HDC hdc;
    HGLRC rc;
    DWORD end;

    wc.lpfnWndProc = DefWindowProcA;
    wc.hInstance = GetModuleHandleA(NULL);
    wc.lpszClassName = "glstereo";
    RegisterClassA(&wc);
    hwnd = CreateWindowA("glstereo", "glstereo", WS_OVERLAPPEDWINDOW | WS_VISIBLE, 0, 0, 416, 339, NULL, NULL, wc.hInstance, NULL);
    hdc = GetDC(hwnd);
    count = DescribePixelFormat(hdc, 1, sizeof(pfd), &pfd);
    for (i = 1; i <= count; i++)
    {
        DescribePixelFormat(hdc, i, sizeof(pfd), &pfd);
        if (!!(pfd.dwFlags & PFD_STEREO) == !mono && (pfd.dwFlags & PFD_DOUBLEBUFFER) && (pfd.dwFlags & PFD_SUPPORT_OPENGL)
            && (pfd.dwFlags & PFD_DRAW_TO_WINDOW) && pfd.iPixelType == PFD_TYPE_RGBA && pfd.cColorBits >= 24)
        {
            format = i;
            break;
        }
    }
    printf("GLSTEREO: %d pixel formats, %s format %d\n", count, mono ? "mono" : "stereo", format);
    if (!format) { printf("GLSTEREO FAIL: no %s pixel format\n", mono ? "mono" : "PFD_STEREO"); return 1; }
    if (!SetPixelFormat(hdc, format, &pfd)) { printf("GLSTEREO FAIL: SetPixelFormat\n"); return 1; }
    rc = wglCreateContext(hdc);
    if (!rc || !wglMakeCurrent(hdc, rc)) { printf("GLSTEREO FAIL: context\n"); return 1; }
    printf("GLSTEREO: %s\n", (const char *)glGetString(GL_RENDERER));
    end = GetTickCount() + seconds * 1000;
    for (i = 0; GetTickCount() < end; i++)
    {
        MSG msg;
        RECT rc2;
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) DispatchMessageA(&msg);
        GetClientRect(hwnd, &rc2);
        glViewport(0, 0, rc2.right, rc2.bottom);
        glDrawBuffer(mono ? GL_BACK : GL_BACK_LEFT);
        glClearColor(1, 0, 0, 1);
        glClear(GL_COLOR_BUFFER_BIT);
        if (!mono)
        {
            glDrawBuffer(GL_BACK_RIGHT);
            glClearColor(0, 1, 0, 1);
            glClear(GL_COLOR_BUFFER_BIT);
        }
        SwapBuffers(hdc);
        if (i == 5) printf("GLSTEREO: ready, client %ldx%ld\n", rc2.right, rc2.bottom), fflush(stdout);
        Sleep(30);
    }
    printf("GLSTEREO: done\n");
    return 0;
}
