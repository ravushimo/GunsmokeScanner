@echo off
REM Renamed to setup.bat - this stub keeps old shortcuts working.
cd /d "%~dp0"
echo [NOTE] compile.bat was renamed to setup.bat - forwarding...
echo.
call "%~dp0setup.bat" %*
