@echo off
call "%~dp0vcvars.bat" || exit /b 1
cd /d "%~dp0"
rem /W4 /WX and /analyze: every warning, the code analysis included, stops the build.
cl /nologo /W4 /WX /analyze /O2 /LD /EHsc channel.cpp input.cpp user32.lib /link /OUT:channel.dll
