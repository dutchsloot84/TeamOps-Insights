@echo off
REM --- SET THIS PATH TO YOUR GIT BASH INSTALLATION ---
SET BASH_EXE="C:\Program Files\Git\bin\bash.exe"
REM --- SET THE PATH TO YOUR SCRIPT ---
SET SCRIPT_PATH="C:\projects\ReleaseCopilot-AI\scripts\get_backlog.sh"

echo Running GitHub Project Backlog Fetcher...

%BASH_EXE% %SCRIPT_PATH%

echo.
pause