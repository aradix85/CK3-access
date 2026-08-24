@echo off
rem Runs the three speech rounds. Python has to be on PATH; the hard-coded interpreter that used
rem to stand here was one person's install path and broke for everyone else.
python "%~dp0test_speech.py"
pause
