@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Setup + build hub (run this first as a new user).
REM Modes: setup (.venv), self (build from .venv), release (cached build venvs).
REM Always pause on success or failure so a double-clicked window stays readable.
REM Use goto around CALL - avoid multi-line IF blocks that abort cmd early.

if /I "%~1"=="setup" goto mode_setup
if /I "%~1"=="self" goto mode_self
if /I "%~1"=="release" goto mode_release

echo ========================================
echo  Gunsmoke Scanner - setup / build
echo ========================================
echo.
:ask_mode
echo What do you want to do?
echo.
echo   1^) Install dependencies  [recommended / default]
echo        Creates .venv, installs Python packages, picks CPU or CUDA
echo        PyTorch for this machine. Run this first. Then use start.bat
echo        to launch from source.
echo.
echo   2^) Build exe ^(CPU or CUDA auto^)
echo        Packages a folder under dist\ using your .venv from option 1.
echo        Picks CPU or CUDA automatically from what option 1 installed.
echo        Requires option 1 to have been run successfully first.
echo.
echo   3^) Build release ^(developers^)
echo        Uses separate cached venvs ^(.venv-build-cpu / .venv-build-cuda^)
echo        so CPU and CUDA toolchains are not redownloaded every time.
echo        Disk: ~1.1 GB CPU cache, ~4.7 GB CUDA cache.
echo.
set "MODE_CHOICE="
set /p "MODE_CHOICE=Choice [1/2/3] (default 1): "
if "%MODE_CHOICE%"=="" set "MODE_CHOICE=1"
set "MODE_CHOICE=%MODE_CHOICE:~0,1%"
if "%MODE_CHOICE%"=="1" goto mode_setup
if "%MODE_CHOICE%"=="2" goto mode_self
if "%MODE_CHOICE%"=="3" goto mode_release
echo Invalid choice. Please enter 1, 2, or 3.
echo.
goto ask_mode

REM ============================================================
:mode_setup
echo.
echo ========================================
echo  Install dependencies
echo ========================================
call :ensure_host_python
if errorlevel 1 goto :die
call :ensure_dev_venv
if errorlevel 1 goto :die
echo.
echo Done. Next steps:
echo   - Run start.bat  to launch from source
echo   - Or run setup.bat again and choose 2 to build an exe
goto :ok

REM ============================================================
:mode_self
echo.
echo ========================================
echo  Build exe from .venv
echo ========================================
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found.
  echo Run setup.bat and choose option 1 ^(Install dependencies^) first.
  goto :die
)

set "VENV_PY=.venv\Scripts\python.exe"
"%VENV_PY%" -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] .venv Python is broken. Re-run option 1 to repair it.
  goto :die
)

for /f "usebackq delims=" %%i in (`"%VENV_PY%" -c "from src.constants import APP_VERSION; print(APP_VERSION)"`) do set "APP_VER=%%i"
if not defined APP_VER set "APP_VER=dev"

REM Name the folder from whatever torch is in .venv
set "SELF_VARIANT=CPU"
"%VENV_PY%" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"
if not errorlevel 1 set "SELF_VARIANT=CUDA"

echo App version: %APP_VER%
echo Using .venv torch as %SELF_VARIANT% build
echo.

call :ask_7zip
call :build_variant %SELF_VARIANT%
if errorlevel 1 goto :die
if "%DO_7Z%"=="1" call :archive_variant %SELF_VARIANT%

echo.
echo ========================================
echo  Done
echo ========================================
echo Folder: dist\GunsmokeScanner-%SELF_VARIANT%\
if "%DO_7Z%"=="1" echo Archive: dist\GunsmokeScanner-%SELF_VARIANT%-v%APP_VER%.7z
goto :ok

REM ============================================================
:mode_release
echo.
echo ========================================
echo  Build release ^(cached venvs / developers^)
echo ========================================
echo Cached venvs use ~1.1 GB ^(CPU^) and ~4.7 GB ^(CUDA^) on disk.
echo They are created once and reused so release builds stay fast.
echo.
:ask_release_variant
echo Which release to build?
echo   1^) CPU only  [default]
echo   2^) CUDA / GPU only  ^(NVIDIA GPUs^)
echo   3^) Both
echo.
set "BUILD_CHOICE="
set /p "BUILD_CHOICE=Choice [1/2/3] (default 1): "
if "%BUILD_CHOICE%"=="" set "BUILD_CHOICE=1"
set "BUILD_CHOICE=%BUILD_CHOICE:~0,1%"

set "DO_CPU=0"
set "DO_CUDA=0"
if "%BUILD_CHOICE%"=="1" set "DO_CPU=1"
if "%BUILD_CHOICE%"=="2" set "DO_CUDA=1"
if "%BUILD_CHOICE%"=="3" set "DO_CPU=1" & set "DO_CUDA=1"
if "%DO_CPU%%DO_CUDA%"=="00" (
  echo Invalid choice. Please enter 1, 2, or 3.
  echo.
  goto ask_release_variant
)

call :ask_7zip

call :ensure_host_python
if errorlevel 1 goto :die

for /f "usebackq delims=" %%i in (`"%HOST_PY%" -c "from src.constants import APP_VERSION; print(APP_VERSION)"`) do set "APP_VER=%%i"
if not defined APP_VER set "APP_VER=dev"
echo App version: %APP_VER%
echo Host Python: %HOST_PY%
if "%DO_CPU%"=="1" if "%DO_CUDA%"=="1" echo Plan: CPU + CUDA
if "%DO_CPU%"=="1" if not "%DO_CUDA%"=="1" echo Plan: CPU only
if not "%DO_CPU%"=="1" if "%DO_CUDA%"=="1" echo Plan: CUDA only
echo.

set "BOOT_ARGS="
if "%DO_CPU%"=="1" set "BOOT_ARGS=!BOOT_ARGS! --cpu"
if "%DO_CUDA%"=="1" set "BOOT_ARGS=!BOOT_ARGS! --cuda"
echo Ensuring cached build venv(s)...
"%HOST_PY%" scripts\bootstrap_build_venvs.py !BOOT_ARGS!
if errorlevel 1 (
  echo [ERROR] Build venv bootstrap failed.
  goto :die
)
echo.

if not "%DO_CPU%"=="1" goto after_cpu
echo ========================================
echo  Building CPU release
echo ========================================
set "VENV_PY=.venv-build-cpu\Scripts\python.exe"
if not exist "!VENV_PY!" (
  echo [ERROR] Missing !VENV_PY!
  goto :die
)
call :build_variant CPU
if errorlevel 1 goto :die
if "%DO_7Z%"=="1" call :archive_variant CPU
echo.
:after_cpu

if not "%DO_CUDA%"=="1" goto after_cuda
echo ========================================
echo  Building CUDA release
echo ========================================
set "VENV_PY=.venv-build-cuda\Scripts\python.exe"
if not exist "!VENV_PY!" (
  echo [ERROR] Missing !VENV_PY!
  goto :die
)
echo Checking CUDA torch in build venv...
"!VENV_PY!" -c "import torch,sys; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); sys.exit(0 if torch.cuda.is_available() else 1)"
if errorlevel 1 (
  echo [ERROR] torch.cuda.is_available^(^) is False in .venv-build-cuda.
  echo CUDA build was NOT created. CPU output is still in dist\ if built.
  goto :die
)
call :build_variant CUDA
if errorlevel 1 goto :die
if "%DO_7Z%"=="1" call :archive_variant CUDA
echo.
:after_cuda

echo ========================================
echo  Done
echo ========================================
if "%DO_CPU%"=="1" echo CPU folder : dist\GunsmokeScanner-CPU\
if "%DO_CUDA%"=="1" echo CUDA folder: dist\GunsmokeScanner-CUDA\
if "%DO_7Z%"=="1" if "%DO_CPU%"=="1" echo Archive    : dist\GunsmokeScanner-CPU-v%APP_VER%.7z
if "%DO_7Z%"=="1" if "%DO_CUDA%"=="1" echo Archive    : dist\GunsmokeScanner-CUDA-v%APP_VER%.7z
goto :ok

REM ============================================================
:ensure_host_python
if exist ".venv\Scripts\python.exe" set "HOST_PY=.venv\Scripts\python.exe"
if not exist ".venv\Scripts\python.exe" set "HOST_PY=python"
"%HOST_PY%" -c "import sys" >nul 2>&1
if not errorlevel 1 goto ensure_host_python_ok
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: No Python found on PATH. Install Python 3.9+ and retry.
  exit /b 1
)
set "HOST_PY=python"
:ensure_host_python_ok
"%HOST_PY%" -c "import sys; print(sys.executable)"
exit /b 0

REM ============================================================
:ensure_dev_venv
if exist ".venv\Scripts\python.exe" goto ensure_dev_venv_pip
echo Creating .venv ...
python -m venv .venv
if errorlevel 1 (
  echo ERROR: Failed to create .venv
  exit /b 1
)
:ensure_dev_venv_pip
set "VENV_PY=.venv\Scripts\python.exe"
echo Installing requirements into .venv ...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: pip install failed.
  exit /b 1
)
echo Selecting CPU vs CUDA PyTorch for .venv ...
"%VENV_PY%" scripts\ensure_torch.py
if errorlevel 1 (
  echo ERROR: Torch setup failed.
  exit /b 1
)
echo .venv ready.
exit /b 0

REM ============================================================
:ask_7zip
echo.
echo Create 7-Zip archives after build?
echo   Y^) Yes
echo   N^) No  [default]
echo.
:ask_7zip_prompt
set "ZIP_CHOICE="
set /p "ZIP_CHOICE=Archive with 7-Zip? [Y/N] (default N): "
if "%ZIP_CHOICE%"=="" set "ZIP_CHOICE=N"
set "ZIP_CHOICE=%ZIP_CHOICE:~0,1%"
set "DO_7Z=0"
set "SEVENZ="
if /I "%ZIP_CHOICE%"=="Y" set "DO_7Z=1"
if /I "%ZIP_CHOICE%"=="N" goto ask_7zip_locate
if "%DO_7Z%"=="1" goto ask_7zip_locate
echo Invalid choice. Please enter Y or N.
echo.
goto ask_7zip_prompt

:ask_7zip_locate
if "%DO_7Z%"=="1" goto ask_7zip_find
echo Skipping 7-Zip archives.
exit /b 0

:ask_7zip_find
where 7z >nul 2>&1 && set "SEVENZ=7z"
if not defined SEVENZ if exist "%ProgramFiles%\7-Zip\7z.exe" set "SEVENZ=%ProgramFiles%\7-Zip\7z.exe"
if not defined SEVENZ if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" set "SEVENZ=%ProgramFiles(x86)%\7-Zip\7z.exe"
if not defined SEVENZ goto ask_7zip_missing
echo Using 7-Zip: !SEVENZ!
exit /b 0

:ask_7zip_missing
echo [WARN] 7-Zip not found - builds will be created but not archived.
echo Install 7-Zip or add 7z.exe to PATH.
set "DO_7Z=0"
exit /b 0

REM ============================================================
:build_variant
set "VARIANT=%~1"
set "NAME=GunsmokeScanner-%VARIANT%"
echo PyInstaller -^> dist\%NAME%\
REM Qt: widgets-only app. Do NOT --collect-all PySide6 (pulls QML/Quick/TTS/
REM WebEngine/Multimedia and thousands of files). PyInstaller hooks for
REM QtWidgets already collect platforms/styles/imageformats plugins.
"!VENV_PY!" -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name "%NAME%" ^
  --icon "assets\icon.ico" ^
  --add-data "src;src" ^
  --add-data "assets;assets" ^
  --hidden-import PIL.ImageQt ^
  --hidden-import PySide6.QtCore ^
  --hidden-import PySide6.QtGui ^
  --hidden-import PySide6.QtWidgets ^
  --hidden-import scipy._external.array_api_compat.numpy.fft ^
  --collect-submodules scipy._external ^
  --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtQuick3D ^
  --exclude-module PySide6.QtQuickControls2 ^
  --exclude-module PySide6.QtQuickWidgets ^
  --exclude-module PySide6.QtMultimedia ^
  --exclude-module PySide6.QtMultimediaWidgets ^
  --exclude-module PySide6.QtWebEngine ^
  --exclude-module PySide6.QtWebEngineCore ^
  --exclude-module PySide6.QtWebEngineWidgets ^
  --exclude-module PySide6.QtWebChannel ^
  --exclude-module PySide6.QtWebSockets ^
  --exclude-module PySide6.QtTextToSpeech ^
  --exclude-module PySide6.QtPdf ^
  --exclude-module PySide6.QtPdfWidgets ^
  --exclude-module PySide6.Qt3DCore ^
  --exclude-module PySide6.Qt3DRender ^
  --exclude-module PySide6.Qt3DInput ^
  --exclude-module PySide6.Qt3DLogic ^
  --exclude-module PySide6.Qt3DAnimation ^
  --exclude-module PySide6.Qt3DExtras ^
  --exclude-module PySide6.QtCharts ^
  --exclude-module PySide6.QtDataVisualization ^
  --exclude-module PySide6.QtGraphs ^
  --exclude-module PySide6.QtBluetooth ^
  --exclude-module PySide6.QtNfc ^
  --exclude-module PySide6.QtPositioning ^
  --exclude-module PySide6.QtLocation ^
  --exclude-module PySide6.QtSensors ^
  --exclude-module PySide6.QtSerialPort ^
  --exclude-module PySide6.QtSerialBus ^
  --exclude-module PySide6.QtRemoteObjects ^
  --exclude-module PySide6.QtDesigner ^
  --exclude-module PySide6.QtHelp ^
  --exclude-module PySide6.QtTest ^
  --exclude-module PySide6.QtSql ^
  --exclude-module PySide6.QtHttpServer ^
  --exclude-module PySide6.QtSpatialAudio ^
  --exclude-module matplotlib ^
  --exclude-module tkinter ^
  main.py
if errorlevel 1 (
  echo [ERROR] PyInstaller failed for %VARIANT%
  exit /b 1
)

echo Note: EasyOCR models are not bundled - they download on first run
echo       into easyocr_models\ next to the exe (English by default).

> "dist\%NAME%\BUILD.txt" echo Gunsmoke Scanner %VARIANT% build v%APP_VER%
>> "dist\%NAME%\BUILD.txt" echo.
if /I "%VARIANT%"=="CUDA" (
  >> "dist\%NAME%\BUILD.txt" echo Requires an NVIDIA GPU + recent Game Ready / Studio drivers.
) else (
  >> "dist\%NAME%\BUILD.txt" echo CPU OCR build - works without an NVIDIA GPU.
)
>> "dist\%NAME%\BUILD.txt" echo.
>> "dist\%NAME%\BUILD.txt" echo EasyOCR models download on first launch into easyocr_models\.
>> "dist\%NAME%\BUILD.txt" echo Run GunsmokeScanner-%VARIANT%.exe

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

REM ============================================================
:ok
echo.
pause
exit /b 0

:die
echo.
echo Stopped with an error.
pause
exit /b 1
