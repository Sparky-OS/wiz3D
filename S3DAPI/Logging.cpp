#include "StdAfx.h"
#include "GlobalData.h"
#include "ReadData.h"
#include "../../CommonUtils/System.h"

void InitializeLogging()
{
	_tcscpy(gInfo.LogFileDirectory, gInfo.DriverDirectory);
	// 0.5.0: centralised log root. All wiz3D-emitted logs (ZLOg master,
	// proxy loader diagnostic logs, shader dumps, hunter captures) live
	// under this folder next to the game exe. Previous "Logs/" folder
	// name was generic enough to clash with game-written folders; the
	// wiz3D_Logs/ prefix makes ownership obvious and lets us delete the
	// whole subtree on uninstall without touching the game's own files.
	PathAppend(gInfo.LogFileDirectory, _T("wiz3D_Logs"));
	CreateDirectory(gInfo.LogFileDirectory, 0);
	PathAppend(gInfo.LogFileDirectory, gInfo.ApplicationName);
	TCHAR* c = _tcsrchr(gInfo.LogFileDirectory, '.');
	if (c != NULL)
		c[0] = '\0';
	CreateDirectory(gInfo.LogFileDirectory, 0);

	//--- LogFileName ---
	_tcscpy(gInfo.LogFileName, gInfo.LogFileDirectory);
	PathAppend(gInfo.LogFileName, gInfo.ApplicationName);
	_tcscat(gInfo.LogFileName, _T(".log"));

	//--- Start ZLOg ---
	// 0.4.1: zlog's namespace itself lives inside #ifdef ZLOG_ALLOW_TRACING
	// in ZLOg/ZLOg.h, so ReopenLogger/InitializeFromXML/IsLoggerOpened are
	// only visible outside FINAL_RELEASE. The path setup above still runs
	// so ShaderHunter / Dumper paths get a valid wiz3D_Logs/<Game>/ root.
#ifdef ZLOG_ALLOW_TRACING
	if ( !zlog::IsLoggerOpened() )
	{
		TCHAR configPath[MAX_PATH];
		GetConfigFullPath(configPath);
		zlog::InitializeFromXML(configPath, _T("Config.ZLOg"));
		zlog::ReopenLogger(gInfo.LogFileName, true);
	}
#endif
}