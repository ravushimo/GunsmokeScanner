@echo off
setlocal
cd /d "%~dp0"

echo Installing Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo pip install failed.
  exit /b 1
)

echo.
echo Selecting CPU vs CUDA PyTorch from GPU detection...
python scripts\ensure_torch.py
if errorlevel 1 (
  echo Torch setup reported an issue — OCR may stay on CPU.
  exit /b 1
)

echo.
echo Done. Start with: python main.py   or   start.bat
endlocal
