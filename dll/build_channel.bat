@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d "%~dp0"
cl /nologo /W3 /O2 /LD /EHsc channel.cpp user32.lib /link /OUT:channel.dll
