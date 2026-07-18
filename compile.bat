@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Build CPU + CUDA onedir releases, then 7-Zip each folder.
REM Requires: .venv with project deps, easyocr_models\ (optional but recommended),
REM           7-Zip on PATH or in Program Files.

set "VENV_PY=.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] Missing .venv\Scripts\python.exe
  echo Create a venv and run install_deps.bat first.
  exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo [ERROR] Could not activate .venv
  exit /b 1
)

REM Locate 7-Zip
set "SEVENZ="
where 7z >nul 2>&1 && set "SEVENZ=7z"
if not defined SEVENZ if exist "%ProgramFiles%\7-Zip\7z.exe" set "SEVENZ=%ProgramFiles%\7-Zip\7z.exe"
if not defined SEVENZ if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" set "SEVENZ=%ProgramFiles(x86)%\7-Zip\7z.exe"
if defined SEVENZ (
  echo Using 7-Zip: %SEVENZ%
) else (
  echo [WARN] 7-Zip not found — builds will be created but not archived.
  echo Install 7-Zip or add 7z.exe to PATH.
)

for /f "usebackq delims=" %%i in (`"%VENV_PY%" -c "from src.constants import APP_VERSION; print(APP_VERSION)"`) do set "APP_VER=%%i"
if not defined APP_VER set "APP_VER=dev"
echo App version: %APP_VER%
echo.

set "TORCH_VER=2.11.0"
set "VISION_VER=0.26.0"

REM ---------- CPU ----------
echo ========================================
echo  Building CPU release
echo ========================================
echo Installing CPU torch...
"%VENV_PY%" -m pip uninstall -y torch torchvision torchaudio >nul 2>&1
"%VENV_PY%" -m pip install "torch==%TORCH_VER%" "torchvision==%VISION_VER%"
if errorlevel 1 (
  echo [ERROR] CPU torch install failed.
  exit /b 1
)

call :build_variant CPU
if errorlevel 1 exit /b 1
call :archive_variant CPU
echo.

REM ---------- CUDA ----------
echo ========================================
echo  Building CUDA release
echo ========================================
echo Installing CUDA torch via scripts\ensure_torch.py ...
"%VENV_PY%" scripts\ensure_torch.py
if errorlevel 1 (
  echo [ERROR] CUDA torch setup failed — CPU build is still in dist\.
  exit /b 1
)

REM Refuse to ship a "CUDA" build that is actually CPU-only
"%VENV_PY%" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"
if errorlevel 1 (
  echo [ERROR] torch.cuda.is_available^(^) is False after ensure_torch.
  echo CUDA archive was NOT built. CPU build is in dist\.
  exit /b 1
)

call :build_variant CUDA
if errorlevel 1 exit /b 1
call :archive_variant CUDA
echo.

echo ========================================
echo  Done
echo ========================================
echo CPU folder : dist\GunsmokeScanner-CPU\
echo CUDA folder: dist\GunsmokeScanner-CUDA\
if defined SEVENZ (
  echo Archives  : dist\GunsmokeScanner-CPU-v%APP_VER%.7z
  echo             dist\GunsmokeScanner-CUDA-v%APP_VER%.7z
)
echo.
pause
exit /b 0

REM ============================================================
:build_variant
set "VARIANT=%~1"
set "NAME=GunsmokeScanner-%VARIANT%"
echo PyInstaller -^> dist\%NAME%\
"%VENV_PY%" -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name "%NAME%" ^
  --icon "assets\icon.ico" ^
  --add-data "src;src" ^
  --add-data "assets;assets" ^
  main.py
if errorlevel 1 (
  echo [ERROR] PyInstaller failed for %VARIANT%
  exit /b 1
)

if exist "easyocr_models\" (
  echo Copying easyocr_models...
  xcopy /E /I /Y "easyocr_models" "dist\%NAME%\easyocr_models\" >nul
) else (
  echo [WARN] easyocr_models\ not found — OCR will download models on first run.
)

REM Small readme inside the folder
>(
  echo Gunsmoke Scanner %VARIANT% build v%APP_VER%
  echo.
  if /I "%VARIANT%"=="CUDA" (
    echo Requires an NVIDIA GPU + recent Game Ready / Studio drivers.
  ) else (
    echo CPU OCR build — works without an NVIDIA GPU.
  )
  echo Run GunsmokeScanner-%VARIANT%.exe
) > "dist\%NAME%\BUILD.txt"

echo Built dist\%NAME%\
exit /b 0

REM ============================================================
:archive_variant
set "VARIANT=%~1"
set "NAME=GunsmokeScanner-%VARIANT%"
set "ARCHIVE=dist\GunsmokeScanner-%VARIANT%-v%APP_VER%.7z"
if not defined SEVENZ exit /b 0
if not exist "dist\%NAME%\" (
  echo [WARN] Nothing to archive for %VARIANT%
  exit /b 0
)
echo Archiving %ARCHIVE% ...
if exist "%ARCHIVE%" del /f /q "%ARCHIVE%"
"%SEVENZ%" a -t7z -mx=7 -mmt=on "%ARCHIVE%" ".\dist\%NAME%"
if errorlevel 1 (
  echo [WARN] 7-Zip failed for %VARIANT%
  exit /b 0
)
echo Archived %ARCHIVE%
exit /b 0
