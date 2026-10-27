@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo [fbhub] Python not found. Install Python 3.10+ and enable "Add Python to PATH".
  pause
  exit /b 1
)

echo === compile ===
python -m compileall -q fbhub tests
if errorlevel 1 goto fail

echo === unit tests ===
python -m unittest discover -s tests -v
if errorlevel 1 goto fail

echo === USB / driver diagnosis ===
python -m fbhub doctor
if errorlevel 1 goto fail

echo.
echo Verification finished. No real fastboot device was flashed.
pause
exit /b 0

:fail
echo.
echo Verification FAILED.
pause
exit /b 1
