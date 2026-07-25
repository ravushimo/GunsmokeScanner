@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py
) else (
  echo [WARN] .venv not found - run setup.bat and choose option 1 first.
  echo Falling back to system python...
  python main.py
)
echo.
pause
