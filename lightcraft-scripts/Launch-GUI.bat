@echo off
rem Opens the LightCraft scripts window without a console.
rem If nothing opens: run  uv run lc_gui.py  in a terminal to see the error.
cd /d "%~dp0"
for /f "delims=" %%p in ('uv python find') do set "PY=%%~dpp"
if not exist "%PY%pythonw.exe" (
  echo pythonw.exe not found next to %PY%
  pause
  exit /b 1
)
start "" "%PY%pythonw.exe" "%~dp0lc_gui.py"
