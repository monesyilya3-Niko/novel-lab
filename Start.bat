@echo off
rem novel-lab portable launcher: find Python and start the GUI workbench.
rem Keep this file ASCII-only: cmd.exe parses .bat in the system ANSI codepage.
setlocal
cd /d "%~dp0"

set "PY="
for %%P in (python py) do (
    where %%P >nul 2>nul && set "PY=%%P" && goto :found
)
echo [novel-lab] Python not found. Install Python 3.10+ from https://www.python.org/downloads/
echo [novel-lab] IMPORTANT: check "Add Python to PATH" during setup.
pause
exit /b 1

:found
echo [novel-lab] Starting GUI workbench with %PY% ...
%PY% -m gui.launch
if errorlevel 1 (
    echo.
    echo [novel-lab] Startup failed. See the error above.
    pause
)
endlocal
