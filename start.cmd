@echo off
setlocal
cd /d "%~dp0"
set "TEMP=%~dp0RuntimeTemp"
set "TMP=%~dp0RuntimeTemp"
if exist "%~dp0Program\EmailAssistant\EmailAssistant.exe" (
    start "" "%~dp0Program\EmailAssistant\EmailAssistant.exe"
) else (
    start "" "%~dp0Runtime\Python3147\pythonw.exe" "%~dp0launch_desktop.py"
)
