@echo off
rem Opens the LightCraft scripts window without a console.
rem If nothing opens: run  uv run lc_gui.py  in a terminal to see the error.
cd /d "%~dp0"
set "PY="

where uv >nul 2>nul
if errorlevel 1 goto :no_uv

rem uv is there: make sure it has a Python, then use its pythonw.exe
uv python find >nul 2>nul
if errorlevel 1 (
  echo No Python found yet: uv will install one, this takes a minute...
  uv python install
  if errorlevel 1 goto :fail
)
for /f "delims=" %%p in ('uv python find') do set "PY=%%~dpp"
if exist "%PY%pythonw.exe" goto :run
goto :fail

:no_uv
rem No uv: try a Python installed from python.org
for /f "delims=" %%p in ('where pythonw 2^>nul') do if not defined PY set "PY=%%~dpp"
if defined PY if exist "%PY%pythonw.exe" goto :run
echo.
echo Neither uv nor Python was found on this computer.
echo Install uv by pasting this line in PowerShell, then close and reopen the window:
echo.
echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo.
echo Then double-click Launch-GUI.bat again.
pause
exit /b 1

:run
start "" "%PY%pythonw.exe" "%~dp0lc_gui.py"
exit /b 0

:fail
echo pythonw.exe not found. Run  uv run lc_gui.py  in a terminal to see the error.
pause
exit /b 1
