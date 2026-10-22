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
#include "StdAfx.h"
#include <Shlobj.h>
#include <Shlwapi.h>
#include "Globals.h"
#include "..\S3DAPI\ReadData.h"
#include "ShaderAnalyzer.h"
#include <tinyxml.h>
#include "CommonUtils/CommonResourceFolders.h"
#include "CommandDumper.h"

void InitDirectories()
{
	// 0.4.1: ungated so zlog file-path setup + Shaders/Dump/DX9/ layout both
	// run in shipped (FINAL_RELEASE) builds. Field diagnostics stay useful.
	InitializeLogging();
	// 0.5.0 layout: wiz3D_Logs/<Game>/Shaders/Dump/DX9/ for mass dumps.
	// Hunter/ sibling folder is reserved for user-captured single-shader
	// reports from the ShaderHunter OSD mode.
	_tcscpy(gData.DumpDirectory, gInfo.LogFileDirectory);
	PathAppend(gData.DumpDirectory, _T("Shaders"));
	CreateDirectory(gData.DumpDirectory, 0);
	PathAppend(gData.DumpDirectory, _T("Dump"));
	CreateDirectory(gData.DumpDirectory, 0);
	PathAppend(gData.DumpDirectory, _T("DX9"));
	CreateDirectory(gData.DumpDirectory, 0);
	ClearDirectory(gData.DumpDirectory);
#ifndef FINAL_RELEASE
	// CCommandDumper (the mass command-trace replay facility) is only
	// compiled in non-FINAL_RELEASE builds — see CommandDumper.h, which
	// stubs out the class under FINAL_RELEASE.
	CCommandDumper::GetInstance().Init();
#endif
}

void InitGammaRamp()
{
	HDC dc = GetDC(0);
	//DEBUG_MESSAGE("DeviceGammaRamp\n");
	//for(int i=0; i< 256; i++)
	//{
	//    DEBUG_MESSAGE("%d;%d;%d;%d\n",i,g_DeviceGammaRamp.red[i],g_DeviceGammaRamp.green[i],g_DeviceGammaRamp.blue[i]);
	//}
	D3DGAMMARAMP IdentityGammaRamp;
	//--- set linear GDI gammaRAMP ---
	for(int i=0; i< 256; i++)
	{
		IdentityGammaRamp.red[i]   = i << 8 | i;
		IdentityGammaRamp.green[i] = i << 8 | i;
		IdentityGammaRamp.blue[i]  = i << 8 | i;
	}
	//--- force to apply gamma and disable NVidia or ATI CPL gamma while app work ---
	IdentityGammaRamp.red[0]   = 1;
	IdentityGammaRamp.green[0] = 1;
	IdentityGammaRamp.blue[0]  = 1;
	SetDeviceGammaRamp(dc, &IdentityGammaRamp);
	//--- we must call function SetDeviceGammaRamp() twice for correct working ---
	IdentityGammaRamp.red[0]   = 0;
	IdentityGammaRamp.green[0] = 0;
	IdentityGammaRamp.blue[0]  = 0;
	SetDeviceGammaRamp(dc, &IdentityGammaRamp);
	ReleaseDC(0, dc);
}
