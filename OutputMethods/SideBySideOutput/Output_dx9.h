/* 
* Project : iZ3D Stereo Driver
* Copyright (C) iZ3D Inc. 2002 - 2010
*/

#pragma once

#include "OutputMethod_dx9.h"
#include <vector>

namespace DX9Output
{

struct ResolutionGap
{
	int Width;
	int Height;
	int Gap;
};

class SideBySideOutput :
	public OutputMethod
{
public:
	SideBySideOutput(DWORD mode, DWORD spanMode);
	virtual ~SideBySideOutput(void);

	virtual UINT	GetOutputChainsNumber();
	virtual HRESULT	Output(CBaseSwapChain* pSwapChain);
	virtual HRESULT InitializeSCData(CBaseSwapChain* pSwapChain);
	virtual void	ReadConfigData(const char* configXml);
	virtual void ModifyPresentParameters(IDirect3D9* pd3d, UINT nAdapter, D3DPRESENT_PARAMETERS* parameters);
private:
	bool	m_FullSideBySide;
	bool	m_KWinDoubles;
	wchar_t m_StatePath[MAX_PATH];
	char m_LastWindowState[MAX_PATH * 3 + 80];
	void WriteWindowState(CBaseSwapChain* pSwapChain);
	bool	m_bCrosseyed;
	std::vector<ResolutionGap>	m_Gap;
	int	m_DefaultGap;
};

}
