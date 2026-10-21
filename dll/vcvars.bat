@rem Sets up MSVC for x64 in the calling shell. vswhere finds it, at the place Microsoft guarantees
@rem for vswhere on every machine with Visual Studio 2017 or later, GitHub's Windows runners included,
@rem so no build names a path of one machine. The build and tests\test_channel.py both call this.
@set "VCVARS="
@for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find VC\Auxiliary\Build\vcvars64.bat`) do @set "VCVARS=%%i"
@if not defined VCVARS (echo vswhere found no MSVC with the x64 tools 1>&2 & exit /b 1)
@call "%VCVARS%" >nul
