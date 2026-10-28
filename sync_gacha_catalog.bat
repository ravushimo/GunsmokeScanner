@echo off
cd /d "%~dp0"
echo Syncing gacha catalogs from Dandegate...
echo.
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\sync_gacha_catalog.py %*
) else (
  echo [WARN] .venv not found - falling back to system python...
  python scripts\sync_gacha_catalog.py %*
)
echo.
pause
