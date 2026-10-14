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
#include "stdafx.h"
#include "WDirect3DCreate9.h"
#include "UMDriverHook.h"
#include "BaseStereoRenderer.h"
//#include "../S3DAPI/ScalingAgent.h"
#include "..\S3DAPI\ShutterAPI.h"
#include <version.h>

#undef D3DPERF_BeginEvent
#undef D3DPERF_EndEvent

void __stdcall DisableCreatingStereoResources()
{
	gInfo.RenderTargetCreationMode = 0;
}

void __stdcall RestoreCreatingStereoResourcesMode()
{
	gInfo.RenderTargetCreationMode = 2;
}

// Diagnostic export: returns the active profile state to proxy callers.
// Used by wiz3D-proxy/{d3d8, d3d9, ddraw} after wrapper init to log a
// single ProfileLoad: line into wiz3D_proxy.log. ANSI out-buffer (proxy
// log format is ANSI). Per-source flags so the log can show whether the
// match came from BaseProfile.xml, CommunityProfile.xml, UserProfile.xml,
// or none (all three 0 means the exe-name fallback fired). User profile
// flag can be true ALONGSIDE Base/Community — User overrides are layered
// on top of any matched base profile.
extern "C" __declspec(dllexport)
void __stdcall wiz3D_GetActiveProfileInfo(char* outName, size_t outNameSize,
                                          int* outBaseMatched,
                                          int* outCommunityMatched,
                                          int* outUserMatched)
{
	if (outName && outNameSize > 0)
	{
		// gInfo.ProfileName is TCHAR (wide on this build). Convert to ANSI
		// for the proxy log. WideCharToMultiByte handles truncation safely.
		WideCharToMultiByte(CP_ACP, 0, gInfo.ProfileName, -1,
			outName, (int)outNameSize, NULL, NULL);
		outName[outNameSize - 1] = '\0';
	}
	if (outBaseMatched)      *outBaseMatched      = gInfo.bMatchedInBase      ? 1 : 0;
	if (outCommunityMatched) *outCommunityMatched = gInfo.bMatchedInCommunity ? 1 : 0;
	if (outUserMatched)      *outUserMatched      = gInfo.bMatchedInUser      ? 1 : 0;
}

BOOL IsVistaSP1()
{
	OSVERSIONINFOEX info = { sizeof(OSVERSIONINFOEX) };
	GetVersionEx((LPOSVERSIONINFO)&info);
	if (info.dwMajorVersion == 6 && info.dwMinorVersion == 0 && info.wServicePackMajor >= 1)
		return TRUE;

	return FALSE;
}

BOOL IsVistaD3D9Dll()
{
	TCHAR d3d9_dll_full_path[MAX_PATH];
	GetSystemDirectory(d3d9_dll_full_path, MAX_PATH);
	_tcscat(d3d9_dll_full_path, _T("\\d3d9.dll"));

	DWORD dwDummy; 
	DWORD dwFVISize = GetFileVersionInfoSize( d3d9_dll_full_path , &dwDummy ); 
	LPBYTE lpVersionInfo = new BYTE[dwFVISize]; 
	GetFileVersionInfo( d3d9_dll_full_path , 0 , dwFVISize , lpVersionInfo ); 
	UINT uLen; 
	VS_FIXEDFILEINFO *lpFfi; 
	VerQueryValue( lpVersionInfo , _T("\\") , (LPVOID *)&lpFfi , &uLen ); 
	DWORD dwFileVersionMS = lpFfi->dwFileVersionMS; 
	DWORD dwFileVersionLS = lpFfi->dwFileVersionLS; 
	delete [] lpVersionInfo;
	DWORD dwMajorVersion = HIWORD(dwFileVersionMS);
	DWORD dwMinorVersion = LOWORD(dwFileVersionMS);
	DWORD dwBuildVersion = HIWORD(dwFileVersionLS);
	DWORD dwQFEVersion   = LOWORD(dwFileVersionLS);
	if (dwMajorVersion == 6 && dwMinorVersion == 0 && (dwBuildVersion >= 6000 && dwBuildVersion <= 6002))
		return TRUE;

	return FALSE;
}

BOOL GetD3D9DllName(TCHAR* dll)
{            
	BOOL LoadDebugRuntime = FALSE;
	HKEY hKey;
	if (RegOpenKeyEx(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Microsoft\\Direct3D", 0, KEY_QUERY_VALUE, &hKey) == ERROR_SUCCESS)
	{
		DWORD Size = sizeof(BOOL);
		RegQueryValueEx(hKey, TEXT("LoadDebugRuntime"),	NULL, NULL,	(LPBYTE)&LoadDebugRuntime, &Size);
	}
	if (LoadDebugRuntime)
	{
		_tcscpy(dll, L"d3d9d.dll");
		return LoadDebugRuntime;
	}
	else
	{
		if(IsVistaSP1() && IsVistaD3D9Dll() && gInfo.FixVistaSP1ResetBug)
		{
			_tcscpy(dll, L"d3d9VistaNoSP1.dll");
			return false;
		}
		else
		{
			_tcscpy(dll, L"d3d9.dll");
			return true;
		}
	}	
}

BOOL GetD3D9DllFullPath(TCHAR dllFullPath[MAX_PATH])
{
 	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	TCHAR name[MAX_PATH], path[MAX_PATH];
	if(GetD3D9DllName(name) || !IsVistaSP1())
	{
		if(GetSystemDirectory(path, MAX_PATH) == 0)
			return FALSE;
	}
	else
	{
		_tcscpy_s(path, MAX_PATH, gInfo.DriverDirectory);
		DEBUG_TRACE1(_T("Using d3d9VistaNoSP1.dll\n") );
	}

	int err = _stprintf_s(dllFullPath, MAX_PATH, L"%s\\%s", path, name);
	if (!_tcscmp(name, _T("d3d9.dll")))
	{
		// A proxy installed as the system's d3d9.dll has the real one beside it as d3d9_real.dll.
		TCHAR realPath[MAX_PATH];
		if (_stprintf_s(realPath, MAX_PATH, L"%s\\d3d9_real.dll", path) >= 0 && PathFileExists(realPath))
			return _tcscpy_s(dllFullPath, MAX_PATH, realPath) == 0;
	}
#ifndef FINAL_RELEASE
	if(!PathFileExists(dllFullPath))
#ifndef WIN64
		err = _stprintf_s(dllFullPath, MAX_PATH, L"%s\\..\\..\\final release\\win32\\%s", path, name);
#else
		err = _stprintf_s(dllFullPath, MAX_PATH, L"%s\\..\\..\\final release\\win64\\%s", path, name);
#endif
#endif
	return err >= 0;
}

bool g_bD3D9DllAlreadyLoaded = false;

HMODULE GetD3D9HMODULE()
{
	TCHAR name[MAX_PATH];
	//GetD3D9DllName(name);
	//HMODULE D3D9Handle = GetModuleHandle(name);
	//if(D3D9Handle)
	//	return D3D9Handle;

	if(GetD3D9DllFullPath(name))
	{
		if (g_bD3D9DllAlreadyLoaded)
			return GetModuleHandle(name);
		else
		{
			g_bD3D9DllAlreadyLoaded = true;
			return LoadLibrary(name);
		}
	}

	return NULL;
}

pfDirect3DCreate WINAPI GetD3D9Creator()
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE(); 
	if (hD3D9Lib)
		return (pfDirect3DCreate)GetProcAddress(hD3D9Lib, "Direct3DCreate9");
	return NULL;
}

pfDirect3DCreateEx WINAPI GetD3D9CreatorEx()
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE(); 
	if (hD3D9Lib)
		return (pfDirect3DCreateEx)GetProcAddress(hD3D9Lib, "Direct3DCreate9Ex");
	return NULL;
}

#define D3D9_VISTA_MODULE_NAME	"DriverD3D9VistaModule"

void GetDriverModuleName(LPSTR ModuleName, LPCSTR Key)
{
	ModuleName[0] = '\0';
#ifndef WIN64
	LPCTSTR key = _T("SOFTWARE\\iZ3D\\iZ3D Driver\\Win32");
#else
	LPCTSTR key = _T("SOFTWARE\\iZ3D\\iZ3D Driver\\Win64");
#endif
	HKEY hDriver;
	LSTATUS status = RegOpenKeyEx(HKEY_CURRENT_USER, key, 0, KEY_READ, &hDriver);
	if (status == ERROR_SUCCESS)
	{
		DWORD Size = MAX_PATH * sizeof(CHAR);
		status = RegQueryValueExA(hDriver, Key, NULL, NULL, (BYTE*)ModuleName, &Size);
		if (status)
			Size = 0;
		ModuleName[Size / sizeof(CHAR)] = 0;
		RegCloseKey(hDriver);
	}
}

void DetectShutterMode()
{
	if(gData.ShutterMode == SHUTTER_MODE_IZ3DKMSERVICE)
	{
		if( FALSE == g_KMShutter.InitShutter() )
			gData.ShutterMode = SHUTTER_MODE_AUTO;
	}

	if (gData.ShutterMode != SHUTTER_MODE_AUTO)
		return;
	
	OSVERSIONINFOEX info = { sizeof(OSVERSIONINFOEX) };
	GetVersionEx((LPOSVERSIONINFO)&info);
	if (info.dwMajorVersion < 6) // XP or less
	{
		DEBUG_MESSAGE(_T("Shutter mode switched to Multi-threaded\n"));
		gData.ShutterMode = SHUTTER_MODE_MULTITHREADED;
	}
	else
	{
		//--- in this case ws suppose that app use only default adapter for shutter --
		if((gInfo.OutputCaps & odShutterModeKMAllowed) && TRUE == g_KMShutter.InitShutter())
		{
			DEBUG_MESSAGE(_T("Shutter mode switched to KM Hook\n"));
			gData.ShutterMode = SHUTTER_MODE_IZ3DKMSERVICE;
		}
		else
		{
			pfDirect3DCreate pDirect3DCreate9 = GetD3D9Creator(); 
			if(pDirect3DCreate9)
			{
				CComPtr<IDirect3D9> pDirect3D9;
				pDirect3D9.Attach((*pDirect3DCreate9)(D3D_SDK_VERSION));
				if (SUCCEEDED(pDirect3D9->CheckDeviceFormat( D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL,	
				D3DFMT_X8R8G8B8, 0, D3DRTYPE_SURFACE, (D3DFORMAT)FOURCC_AQBS)))
				{
					DEBUG_MESSAGE(_T("Shutter mode switched to ATI QuadBuffer\n"));
					gData.ShutterMode = SHUTTER_MODE_ATIQB;
				}
				else
				{
					DEBUG_MESSAGE(_T("Shutter mode switched to UM Hook\n"));
					CHAR	DriverDllDX9Name[MAX_PATH];
					GetDriverModuleName(DriverDllDX9Name, D3D9_VISTA_MODULE_NAME);
					if (DriverDllDX9Name[0] != '\0')
						gData.ShutterMode = SHUTTER_MODE_UMHOOK_D3D9;
					else
					{
						DEBUG_MESSAGE(_T("ERROR: Access denied to UM Driver name\n"));
						gData.ShutterMode = SHUTTER_MODE_MULTITHREADED;
					}
				}
			}
			else
				gData.ShutterMode = SHUTTER_MODE_DISABLED;
		}
	}
}

void HookUM()
{
	if (USE_UM_PRESENTER || USE_IZ3DKMSERVICE_PRESENTER)
	{
		if (OpenAdapterNext == NULL)
		{
			CHAR	DriverDllDX9Path[MAX_PATH];
			CHAR	DriverDllDX9Name[MAX_PATH];
			GetDriverModuleName(DriverDllDX9Name, D3D9_VISTA_MODULE_NAME);
			if (DriverDllDX9Name[0] != '\0')
			{
				GetSystemDirectoryA(DriverDllDX9Path, MAX_PATH);
				PathAppendA(DriverDllDX9Path, DriverDllDX9Name);
				HookAPI(DriverDllDX9Path, "OpenAdapter", OpenAdapterCallback, (PVOID*) &OpenAdapterNext, NO_SAFE_UNHOOKING);
				//HookAPI("GDI32.dll", "D3DKMTCreateDevice", D3DKMTCreateDeviceCallback, (PVOID*) &D3DKMTCreateDeviceNext, NO_SAFE_UNHOOKING | DONT_RENEW_OVERWRITTEN_HOOK);
				//HookAPI("GDI32.dll", "D3DKMTPresent", D3DKMTPresentCallback, (PVOID*) &D3DKMTPresentNext, NO_SAFE_UNHOOKING | DONT_RENEW_OVERWRITTEN_HOOK);
			}
			else
				gData.ShutterMode = SHUTTER_MODE_DISABLED;
		}
	}
}

// Per-process serial counter for Direct3DCreate9{Ex} calls. Diagnostic only —
// games like GRFS issue 5 sequential Direct3DCreate9 calls as part of
// capability probing, and the serial lets us correlate the wrapper instance
// in the log with the call that produced it.
static volatile LONG g_Create9SerialCounter = 0;

IDirect3D9* WINAPI WDirect3DCreate9(UINT SDKVersion)
{
	HRESULT hResult = S_OK;

	// Defensive: idempotent. InitializeExchangeServer normally runs first
	// (called by the proxy right after LoadLibraryW), but if any path skips
	// it we still need the deferred init done before HookUM/Direct3DCreate.
	EnsureWrapperInitialized();

	HookUM();

	const LONG serial = InterlockedIncrement(&g_Create9SerialCounter);

	if (IS_D3D9EX_PRESENTER) // 9Ex
	{
		pfDirect3DCreateEx pDirect3DCreate9Ex = GetD3D9CreatorEx();
		if(pDirect3DCreate9Ex)
		{
			CComPtr<IDirect3D9Ex> pDirect3D9Ex;
			HRESULT hr = pDirect3DCreate9Ex(SDKVersion, &pDirect3D9Ex);
			if (SUCCEEDED(hr))
			{
				IDirect3D9 *pReturnedDirect3D9 = 0;
				CDirect3D9* pDirectWrapper = DNew CDirect3D9();
				pDirectWrapper->DoInitialize(pDirect3D9Ex, EXMODE_EMULATE);
				pDirectWrapper->AddRef();
				if(gInfo.RouterType == ROUTER_TYPE_HOOK)
					pReturnedDirect3D9 = pDirect3D9Ex;
				else
					pReturnedDirect3D9 = (IDirect3D9*)pDirectWrapper;
				D9Log("WDirect3DCreate9 #%ld (9Ex path): real=%p -> CDirect3D9=%p (sameRealRefs=%zu)\n",
					(long)serial, (void*)(IDirect3D9Ex*)pDirect3D9Ex, (void*)pDirectWrapper,
					g_pDirectWrapperList.CountByReal(pDirect3D9Ex));
				//ScalingAgent::Instance()->RegisterDirect3D9(pReturnedDirect3D9);
				return pReturnedDirect3D9;
			}
		}
	}

	pfDirect3DCreate pDirect3DCreate9 = GetD3D9Creator();
	if(pDirect3DCreate9)
	{
		CComPtr<IDirect3D9> pDirect3D9;
		pDirect3D9.Attach((*pDirect3DCreate9)(SDKVersion));
		IDirect3D9 *pReturnedDirect3D9 = 0;
		CDirect3D9* pDirectWrapper = DNew CDirect3D9();
		pDirectWrapper->DoInitialize(pDirect3D9, EXMODE_NONE);
		pDirectWrapper->AddRef();
		if(gInfo.RouterType == ROUTER_TYPE_HOOK)
			pReturnedDirect3D9 = pDirect3D9;
		else
			pReturnedDirect3D9 = (IDirect3D9*)pDirectWrapper;
		D9Log("WDirect3DCreate9 #%ld: real=%p -> CDirect3D9=%p (sameRealRefs=%zu)\n",
			(long)serial, (void*)(IDirect3D9*)pDirect3D9, (void*)pDirectWrapper,
			g_pDirectWrapperList.CountByReal(pDirect3D9));
		//ScalingAgent::Instance()->RegisterDirect3D9(pReturnedDirect3D9);
		return pReturnedDirect3D9;
	}
	return NULL;
}

HRESULT WINAPI WDirect3DCreate9Ex(UINT SDKVersion, IDirect3D9Ex **ppD3D)
{
	HRESULT hResult = E_FAIL;

	EnsureWrapperInitialized();

	HookUM();

	const LONG serial = InterlockedIncrement(&g_Create9SerialCounter);

	pfDirect3DCreateEx pDirect3DCreate9Ex = GetD3D9CreatorEx();
	if(pDirect3DCreate9Ex)
	{
		CComPtr<IDirect3D9Ex> pDirect3D9Ex;
		HRESULT hr = pDirect3DCreate9Ex(SDKVersion, &pDirect3D9Ex);
		if (SUCCEEDED(hr))
		{
			*ppD3D = 0;
			CDirect3D9* pDirectWrapper = DNew CDirect3D9();
			pDirectWrapper->DoInitialize(pDirect3D9Ex, EXMODE_EX);
			pDirectWrapper->AddRef();
			if(gInfo.RouterType == ROUTER_TYPE_HOOK)
				*ppD3D = pDirect3D9Ex;
			else
				*ppD3D = (IDirect3D9Ex*)pDirectWrapper;
			if (*ppD3D)
				hResult = S_OK;
			D9Log("WDirect3DCreate9Ex #%ld: real=%p -> CDirect3D9=%p (sameRealRefs=%zu)\n",
				(long)serial, (void*)(IDirect3D9Ex*)pDirect3D9Ex, (void*)pDirectWrapper,
				g_pDirectWrapperList.CountByReal(pDirect3D9Ex));
			//ScalingAgent::Instance()->RegisterDirect3D9(*ppD3D);
		}
		else
			hResult = hr;
	}
	return hResult;
}

// for full wrapping

typedef int (WINAPI *pfD3DPERF_BeginEvent)( D3DCOLOR col, LPCWSTR wszName );
int WINAPI WD3DPERF_BeginEvent( D3DCOLOR col, LPCWSTR wszName )
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE(); 
	if (hD3D9Lib)
	{
		pfD3DPERF_BeginEvent fn = (pfD3DPERF_BeginEvent)GetProcAddress(hD3D9Lib, "D3DPERF_BeginEvent");
		return fn(col, wszName);
	}
	return 0;
}

typedef int (WINAPI *pfD3DPERF_EndEvent)( void );
int WINAPI WD3DPERF_EndEvent( void )
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE(); 
	if (hD3D9Lib)
	{
		pfD3DPERF_EndEvent fn = (pfD3DPERF_EndEvent)GetProcAddress(hD3D9Lib, "D3DPERF_EndEvent");
		return fn();
	}
	return 0;
}

typedef void (WINAPI *pfD3DPERF_SetMarker)( D3DCOLOR col, LPCWSTR wszName );
void WINAPI WD3DPERF_SetMarker( D3DCOLOR col, LPCWSTR wszName )
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE();
	if (hD3D9Lib)
	{
		pfD3DPERF_SetMarker fn = (pfD3DPERF_SetMarker)GetProcAddress(hD3D9Lib, "D3DPERF_SetMarker");
		fn(col, wszName);
	}
}

typedef void (WINAPI *pfD3DPERF_SetRegion)( D3DCOLOR col, LPCWSTR wszName );
void WINAPI WD3DPERF_SetRegion( D3DCOLOR col, LPCWSTR wszName )
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE(); 
	if (hD3D9Lib)
	{
		pfD3DPERF_SetRegion fn = (pfD3DPERF_SetRegion)GetProcAddress(hD3D9Lib, "D3DPERF_SetRegion");
		fn(col, wszName);
	}
}

typedef BOOL (WINAPI *pfD3DPERF_QueryRepeatFrame)( void );
BOOL WINAPI WD3DPERF_QueryRepeatFrame( void )
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE(); 
	if (hD3D9Lib)
	{
		pfD3DPERF_QueryRepeatFrame fn = (pfD3DPERF_QueryRepeatFrame)GetProcAddress(hD3D9Lib, "D3DPERF_QueryRepeatFrame");
		return fn();
	}
	return FALSE;
}

typedef void (WINAPI *pfD3DPERF_SetOptions)( DWORD dwOptions );
void WINAPI WD3DPERF_SetOptions( DWORD dwOptions )
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE(); 
	if (hD3D9Lib)
	{
		pfD3DPERF_SetOptions fn = (pfD3DPERF_SetOptions)GetProcAddress(hD3D9Lib, "D3DPERF_SetOptions");
		fn(dwOptions);
	}
}

typedef DWORD (WINAPI *pfD3DPERF_GetStatus)( void );
DWORD WINAPI WD3DPERF_GetStatus( void )
{
	DEBUG_TRACE1(_T("Entering %s\n"), _T( __FUNCTION__ ) );
	HMODULE hD3D9Lib = GetD3D9HMODULE(); 
	if (hD3D9Lib)
	{
		pfD3DPERF_GetStatus fn = (pfD3DPERF_GetStatus)GetProcAddress(hD3D9Lib, "D3DPERF_GetStatus");
		return fn();
	}
	return FALSE;
}
