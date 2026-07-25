@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Unified setup + build hub.
REM Modes: setup (.venv), self (build with .venv), release (cached build venvs).
REM Always pause on success or failure so a double-clicked window stays readable.
REM Use goto around CALL - avoid multi-line IF blocks that abort cmd early.

if /I "%~1"=="setup" goto mode_setup
if /I "%~1"=="self" goto mode_self
if /I "%~1"=="release" goto mode_release

echo ========================================
echo  Gunsmoke Scanner
echo ========================================
echo.
echo What do you want to do?
echo   1^) Setup .venv  - install deps to run from source  [default]
echo   2^) Build for yourself  - PyInstaller using .venv
echo   3^) Build release  - CPU/CUDA from cached build venvs ^(devs^)
echo        disk: CPU ~1.1 GB, CUDA ~4.7 GB per cached venv
echo.
set "MODE_CHOICE="
set /p "MODE_CHOICE=Choice [1/2/3] (default 1): "
if "%MODE_CHOICE%"=="" set "MODE_CHOICE=1"
set "MODE_CHOICE=%MODE_CHOICE:~0,1%"
if "%MODE_CHOICE%"=="1" goto mode_setup
if "%MODE_CHOICE%"=="2" goto mode_self
if "%MODE_CHOICE%"=="3" goto mode_release
echo [ERROR] Invalid choice. Use 1, 2, or 3.
goto :die

REM ============================================================
:mode_setup
echo.
echo ========================================
echo  Setup .venv
echo ========================================
call :ensure_host_python
if errorlevel 1 goto :die
call :ensure_dev_venv
if errorlevel 1 goto :die
echo.
echo Done. Run start.bat  or  .venv\Scripts\python.exe main.py
goto :ok

REM ============================================================
:mode_self
echo.
echo ========================================
echo  Build for yourself ^(.venv^)
echo ========================================
call :ensure_host_python
if errorlevel 1 goto :die
call :ensure_dev_venv
if errorlevel 1 goto :die

set "VENV_PY=.venv\Scripts\python.exe"
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
if errorlevel 1 goto :die

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
echo  Build release ^(cached venvs^)
echo ========================================
echo Cached venvs use ~1.1 GB ^(CPU^) and ~4.7 GB ^(CUDA^) on disk.
echo.
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
  echo [ERROR] Invalid choice. Use 1, 2, or 3.
  goto :die
)

call :ask_7zip
if errorlevel 1 goto :die

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
set "ZIP_CHOICE="
set /p "ZIP_CHOICE=Archive with 7-Zip? [Y/N] (default N): "
if "%ZIP_CHOICE%"=="" set "ZIP_CHOICE=N"
set "ZIP_CHOICE=%ZIP_CHOICE:~0,1%"
set "DO_7Z=0"
set "SEVENZ="
if /I "%ZIP_CHOICE%"=="Y" set "DO_7Z=1"
if /I "%ZIP_CHOICE%"=="N" goto ask_7zip_locate
if "%DO_7Z%"=="1" goto ask_7zip_locate
echo [ERROR] Invalid archive choice. Use Y or N.
exit /b 1

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
"!VENV_PY!" -m PyInstaller --noconfirm --clean --onedir --windowed ^
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
)

if not exist "easyocr_models\" (
  echo [WARN] easyocr_models\ not found - OCR will download models on first run.
)

> "dist\%NAME%\BUILD.txt" echo Gunsmoke Scanner %VARIANT% build v%APP_VER%
>> "dist\%NAME%\BUILD.txt" echo.
if /I "%VARIANT%"=="CUDA" (
  >> "dist\%NAME%\BUILD.txt" echo Requires an NVIDIA GPU + recent Game Ready / Studio drivers.
) else (
  >> "dist\%NAME%\BUILD.txt" echo CPU OCR build - works without an NVIDIA GPU.
)
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
