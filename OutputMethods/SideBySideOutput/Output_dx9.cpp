/* IZ3D_FILE: $Id$ 
*
* Project : iZ3D Stereo Driver
* Copyright (C) iZ3D Inc. 2002 - 2010
*
* $Author$
* $Revision$
* $Date$
* $LastChangedBy$
* $URL$
*/
// Output.cpp : Defines the entry point for the DLL application.
//

#include "stdafx.h"
#include "Output_dx9.h"
#include "S3DWrapper9\BaseSwapChain.h"
#include "..\OutputLib\FullSideBySide.h"
#include <tinyxml.h>

using namespace DX9Output;

#ifdef _MANAGED
#pragma managed(push, off)
#endif

BOOL APIENTRY DllMain( HMODULE hModule,
					   DWORD  ul_reason_for_call,
					   LPVOID lpReserved
					 )
{
	switch (ul_reason_for_call)
	{
	case DLL_PROCESS_ATTACH:
	case DLL_THREAD_ATTACH:
	case DLL_THREAD_DETACH:
	case DLL_PROCESS_DETACH:
		break;
	}
	return TRUE;
}

#ifdef _MANAGED
#pragma managed(pop)
#endif

OUTPUT_API void* CALLBACK CreateOutputDX9(DWORD mode, DWORD spanMode)
{
	return new SideBySideOutput(mode, spanMode);
}

OUTPUT_API DWORD CALLBACK GetOutputCaps()
{
	return 0;
}

OUTPUT_API void CALLBACK GetOutputName(char* name, DWORD size)
{
	strcpy_s(name, size, "SideBySide");
}

OUTPUT_API BOOL CALLBACK EnumOutputModes(DWORD num, char* name, DWORD size)
{
	switch(num)
	{
	case 0:
		strcpy_s(name, size, "Default");
		return TRUE;
	case 1:
		strcpy_s(name, size, "Over/Under");
		return TRUE;
	case 2:
		strcpy_s(name, size, "Crosseyed");
		return TRUE;
	case 3:
		strcpy_s(name, size, "Full side by side, left first (DX9)");
		return TRUE;
	default:
		return FALSE;
	}
}

SideBySideOutput::SideBySideOutput(DWORD mode, DWORD spanMode)
: OutputMethod(mode, spanMode), m_FullSideBySide(mode == 3), m_bCrosseyed(false), m_DefaultGap(0)
{
	m_StatePath[0] = 0;
	m_LastWindowState[0] = 0;
	m_KWinDoubles = GetEnvironmentVariableW(L"WIZ3D_KWIN_DOUBLES", NULL, 0) != 0;
	if (m_FullSideBySide)
	{
		if (GetEnvironmentVariableW(L"WIZ3D_STEREO_STATE", m_StatePath, MAX_PATH) >= MAX_PATH - 4)
			m_StatePath[0] = 0;
		m_OutputMode = 0;
		m_SpanMode = 1;
	}
	else if (mode != 2)
	{
		m_OutputMode &= 1;
	}
	else
	{
		m_bCrosseyed = true;
		m_OutputMode = 0;
	}
	m_Caps = ocHardwareMouseCursorNotSupported;
}

void SideBySideOutput::ModifyPresentParameters(IDirect3D9* pd3d, UINT nAdapter, D3DPRESENT_PARAMETERS* parameters)
{
	if (!m_FullSideBySide)
	{
		OutputMethod::ModifyPresentParameters(pd3d, nAdapter, parameters);
		return;
	}

	// KWin consumes a window containing two complete eyes; no wide display mode is needed.
	parameters[0].Windowed = TRUE;
	parameters[0].FullScreen_RefreshRateInHz = 0;
	OutputMethod::ModifyPresentParameters(pd3d, nAdapter, parameters);
	HWND window = parameters[0].hDeviceWindow;
	// KWin doubles the declared window itself, so the window keeps one eye's width.
	RECT rect = { 0, 0, (LONG)parameters[0].BackBufferWidth / (m_KWinDoubles ? 2 : 1), (LONG)parameters[0].BackBufferHeight };
	AdjustWindowRectEx(&rect, GetWindowLong(window, GWL_STYLE), GetMenu(window) != NULL,
		GetWindowLong(window, GWL_EXSTYLE));
	SetWindowPos(window, NULL, 0, 0, rect.right - rect.left, rect.bottom - rect.top,
		SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
	// The mark tells that the client area holds both eyes.
	if (!m_KWinDoubles)
		SetPropW(window, kFullSideBySideWindow, (HANDLE)1);
}

UINT DX9Output::SideBySideOutput::GetOutputChainsNumber()
{
	return 1;
}

HRESULT SideBySideOutput::InitializeSCData(CBaseSwapChain* pSwapChain)
{
	HRESULT hResult = OutputMethod::InitializeSCData(pSwapChain);
	if(SUCCEEDED(hResult))
	{
		D3DSURFACE_DESC desc;
		pSwapChain->m_pPrimaryBackBuffer->GetDesc(&desc);
		pSwapChain->m_CurrentGap = m_FullSideBySide ? 0 : m_DefaultGap;
		for (int i = 0; i < (int)m_Gap.size(); i++)
		{
			if (m_FullSideBySide)
				break;
			if (desc.Width == m_Gap[i].Width && desc.Height == m_Gap[i].Height)
			{
				pSwapChain->m_CurrentGap = m_Gap[i].Gap;
				break;
			}
		}
		if (m_FullSideBySide)
			WriteWindowState(pSwapChain);
	}
	return hResult;
}

void SideBySideOutput::WriteWindowState(CBaseSwapChain* pSwapChain)
{
	if (!m_StatePath[0])
		return;
	D3DSURFACE_DESC desc;
	if (FAILED(pSwapChain->m_pPrimaryBackBuffer->GetDesc(&desc)))
		return;
	ULONG_PTR xid = (ULONG_PTR)GetPropW(pSwapChain->GetAppWindow(), L"__wine_x11_whole_window");
	wchar_t exe[MAX_PATH];
	if (!GetModuleFileNameW(NULL, exe, MAX_PATH))
		return;
	const wchar_t* name = wcsrchr(exe, L'\\');
	name = name ? name + 1 : exe;
	char utf8[MAX_PATH * 3];
	if (!WideCharToMultiByte(CP_UTF8, 0, name, -1, utf8, sizeof(utf8), NULL, NULL))
		return;
	char record[MAX_PATH * 3 + 80];
	int size = sprintf_s(record, "wiz3d-full-sbs-v1 %lu %lu %llu\n%s\n", desc.Width, desc.Height, (unsigned long long)xid, utf8);
	if (strcmp(record, m_LastWindowState) == 0)
		return;
	wchar_t temporary[MAX_PATH];
	swprintf_s(temporary, L"%s.tmp", m_StatePath);
	HANDLE file = CreateFileW(temporary, GENERIC_WRITE, FILE_SHARE_READ, NULL,
		CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
	if (file != INVALID_HANDLE_VALUE)
	{
		DWORD written;
		BOOL success = WriteFile(file, record, size, &written, NULL);
		CloseHandle(file);
		if (success && written == (DWORD)size && MoveFileExW(temporary, m_StatePath, MOVEFILE_REPLACE_EXISTING))
			strcpy_s(m_LastWindowState, record);
	}
}

void SideBySideOutput::ReadConfigData( const char* configXml )
{
	// Re-parse with our own (ticpp-shim) TinyXML so no node crosses from S3DAPI.
	if (!configXml || !*configXml)
		return;
	TiXmlDocument doc;
	doc.Parse(configXml);
	if (doc.Error())
		return;
	TiXmlElement* item = doc.RootElement();
	if (!item)
		return;
	TiXmlElement* pitem = item->FirstChildElement("Gap");
	while (pitem)
	{
		ResolutionGap val = { 0, 0, 0 };
		pitem->QueryIntAttribute("Width", &val.Width);
		pitem->QueryIntAttribute("Height", &val.Height);
		pitem->QueryIntAttribute("Value", &val.Gap);
		if (val.Width == 0 && val.Height == 0)
			m_DefaultGap = val.Gap;
		else
			m_Gap.push_back(val);
		pitem = pitem->NextSiblingElement("Gap");
	}
}

SideBySideOutput::~SideBySideOutput(void)
{
	if (m_StatePath[0])
		DeleteFileW(m_StatePath);
}

HRESULT SideBySideOutput::Output(CBaseSwapChain* pSwapChain)
{
	if (m_FullSideBySide)
		WriteWindowState(pSwapChain);
	HRESULT hResult = S_OK;
	IDirect3DSurface9* left = pSwapChain->GetLeftBackBufferRT();
	IDirect3DSurface9* right = pSwapChain->GetRightBackBufferRT();
	RECT* pLeftRect = pSwapChain->GetLeftBackBufferRect();
	RECT* pRightRect = pSwapChain->GetRightBackBufferRect();
	
	IDirect3DSurface9* primary = pSwapChain->m_pPrimaryBackBuffer;
	IDirect3DSurface9* secondary = pSwapChain->m_pSecondaryBackBuffer;
	D3DSURFACE_DESC desc;
	primary->GetDesc(&desc);
	if (m_bCrosseyed || pSwapChain->m_CurrentGap != 0) {
		NSCALL(m_pd3dDevice->ColorFill(primary, NULL, 0));
	}
	RECT Rect;
	Rect.left = 0;
	Rect.top = 0;

	int horizontalGap = 0;
	int verticalGap = 0;
	if ( pSwapChain->m_pSourceRect ){
		horizontalGap = pLeftRect->right - pLeftRect->left + pSwapChain->m_pSourceRect->left - pSwapChain->m_pSourceRect->right;
		verticalGap = pLeftRect->bottom - pLeftRect->top + pSwapChain->m_pSourceRect->top - pSwapChain->m_pSourceRect->bottom;
	}
	// make left eye
	if(m_OutputMode == 0)
	{
		Rect.right = desc.Width / 2 - pSwapChain->m_CurrentGap / 2;
		Rect.bottom = desc.Height;
	}
	else
	{
		Rect.right = desc.Width;
		Rect.bottom = desc.Height / 2 - pSwapChain->m_CurrentGap / 2;
	}

	if (!m_bCrosseyed)
	{
		NSCALL(m_pd3dDevice->StretchRect(left, pLeftRect, 
			primary, &Rect, D3DTEXF_LINEAR));
	}
	else
	{
		float aspect = 1.0f * desc.Width / desc.Height;
		if(m_OutputMode == 0)
		{
			float Offset = (desc.Height - Rect.right / aspect) / 2;
			Rect.top = (DWORD)(Offset + 0.5f);
			Rect.bottom = (DWORD)(desc.Height - Offset + 0.5f);
		}
		else
		{
			float Offset = (desc.Width - Rect.bottom * aspect) / 2;
			Rect.left = (DWORD)(Offset + 0.5f);
			Rect.right = (DWORD)(desc.Width - Offset + 0.5f);
		}
		NSCALL(m_pd3dDevice->StretchRect(right, pRightRect, 
			primary, &Rect, D3DTEXF_LINEAR));
	}


	// make right eye
	if( m_OutputMode == 0 )
	{
		Rect.left = desc.Width / 2 + (pSwapChain->m_CurrentGap - pSwapChain->m_CurrentGap / 2 - horizontalGap/2);
		Rect.right = desc.Width - horizontalGap / 2;
	}
	else
	{
		Rect.top = desc.Height / 2 + (pSwapChain->m_CurrentGap - pSwapChain->m_CurrentGap / 2 - verticalGap / 2);
		Rect.bottom = desc.Height - verticalGap / 2;
	}

	if (!m_bCrosseyed)
	{
		NSCALL(m_pd3dDevice->StretchRect(right, pRightRect, 
			primary, &Rect, D3DTEXF_LINEAR));
	}
	else 
	{
		NSCALL(m_pd3dDevice->StretchRect(left, pLeftRect, 
			primary, &Rect, D3DTEXF_LINEAR));
	}
	return hResult;
}
