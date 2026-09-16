@echo off
cd /d "%~dp0"
title SmartFlow
echo.
echo SmartFlow starting...
echo Folder: %CD%
echo.

if exist app.py goto HASAPP
echo ERROR: app.py not found.
echo Put start.bat in the crypto_smc folder next to app.py.
echo.
pause
exit /b 1

:HASAPP
if exist launch.py goto HASLAUNCH
echo ERROR: launch.py not found.
echo.
pause
exit /b 1

:HASLAUNCH
py -3 -c "import sys" >nul 2>&1
if errorlevel 1 goto TRYPUREPY
echo Using: py -3
py -3 launch.py
goto DONE

:TRYPUREPY
py -c "import sys" >nul 2>&1
if errorlevel 1 goto TRYPYTHON
echo Using: py
py launch.py
goto DONE

:TRYPYTHON
python -c "import sys" >nul 2>&1
if errorlevel 1 goto TRYPYTHON3
echo Using: python
python launch.py
goto DONE

:TRYPYTHON3
python3 -c "import sys" >nul 2>&1
if errorlevel 1 goto NOPY
echo Using: python3
python3 launch.py
goto DONE

:NOPY
echo.
echo ERROR: Python was not found.
echo 1. Download Python from https://www.python.org/downloads/
echo 2. During setup CHECK the box: Add python.exe to PATH
echo 3. Close this window and double-click start.bat again
echo.

:DONE
echo.
pause
