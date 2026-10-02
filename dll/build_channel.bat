@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d "%~dp0"
rem /W4 /WX and /analyze: every warning, the code analysis included, stops the build. sscanf is
rem used on purpose, always with a %n that all_read checks, so its deprecation warning is off.
cl /nologo /W4 /WX /analyze /D_CRT_SECURE_NO_WARNINGS /O2 /LD /EHsc channel.cpp user32.lib /link /OUT:channel.dll
