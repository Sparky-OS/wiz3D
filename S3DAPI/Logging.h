/* 
* Project : iZ3D Stereo Driver
* Copyright (C) iZ3D Inc. 2002 - 2010
*/

#pragma once

#include "S3DAPI.h"
#if !defined(FINAL_RELEASE) && !defined(DEBUGANALYSING) // && !defined(OUTPUT_LIBRARY)
#	define ZLOG_ALLOW_TRACING
#	ifdef _DEBUG
//#		define ZLOG_PRINT_FILE_AND_LINE
#	endif
#endif

#include "../ZLOg/ZLOg.h"
#include "EnumToString.h"

// 0.4.1: InitializeLogging stays exported regardless of FINAL_RELEASE so
// zlog's log-file path (gInfo.LogFileDirectory / LogFileName) is wired up
// in every build. Call-sites in S3DAPI/dllmain.cpp, S3DWrapper9/Globals.cpp
// and S3DWrapper10/S3DWrapperD3D10.cpp are all ungated.
void S3DAPI_API InitializeLogging();
