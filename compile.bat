@echo off
echo Activate virtual environment...
call .venv\Scripts\activate

echo Building Gunsmoke Scanner...
cd /d "%~dp0"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --name "GunsmokeScanner" --add-data "src;src" --add-data "assets;assets" main.py

echo Copying EasyOCR models...
xcopy /E /I /Y "easyocr_models" "dist\GunsmokeScanner\easyocr_models"

echo Done! Find your app in dist\GunsmokeScanner
pause