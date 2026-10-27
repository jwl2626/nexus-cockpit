@echo off
setlocal
cd /d "%~dp0fastbootCmds"
title Publish fastbootCmds to GitHub

echo ==================================================
echo   Publish fastbootCmds to GitHub
echo ==================================================
echo.

git --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] git not found.
    echo         Install: winget install --id Git.Git -e
    echo.
    pause
    exit /b 1
)

rem ---------- identity: ask instead of aborting ----------
git config user.name >nul 2>nul
if errorlevel 1 goto need_identity
git config user.email >nul 2>nul
if errorlevel 1 goto need_identity
goto identity_ok

:need_identity
echo [SETUP] Git identity is not configured yet. Press Enter to accept the default.
echo.
set "GITNAME="
set /p GITNAME=  user.name  [jwl2626]: 
if "%GITNAME%"=="" set "GITNAME=jwl2626"
set "GITMAIL="
set /p GITMAIL=  user.email [52487156+jwl2626@users.noreply.github.com]: 
if "%GITMAIL%"=="" set "GITMAIL=52487156+jwl2626@users.noreply.github.com"
git config --global user.name "%GITNAME%"
git config --global user.email "%GITMAIL%"
echo.
echo   saved: %GITNAME% ^<%GITMAIL%^>
echo.

:identity_ok
echo [1/4] init repository
if not exist ".git" git init -b main

echo [2/4] commit files
git add -A
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "feat: fastbootCmds initial commit" >nul
    echo       committed.
) else (
    echo       nothing new to commit.
)

echo [3/4] link remote
set "GHUSER="
set /p GHUSER=  Your GitHub username [jwl2626]: 
if "%GHUSER%"=="" set "GHUSER=jwl2626"

git remote get-url origin >nul 2>nul
if errorlevel 1 (
    git remote add origin https://github.com/%GHUSER%/fastbootCmds.git
) else (
    git remote set-url origin https://github.com/%GHUSER%/fastbootCmds.git
)
echo       origin = https://github.com/%GHUSER%/fastbootCmds.git

echo.
echo [4/4] push
echo       Make sure this repo exists and is EMPTY ^(no README^):
echo       https://github.com/%GHUSER%/fastbootCmds
echo.
pause
git push -u origin main

if errorlevel 1 (
    echo.
    echo [FAILED] See checklist:
    echo   1. Repo created?   https://github.com/%GHUSER%/fastbootCmds
    echo   2. Wrong account?  browser login must be %GHUSER%
    echo   3. Auth issue?     git credential-manager configure
    echo   4. Repo not empty? git pull --rebase origin main
    echo.
) else (
    echo.
    echo [DONE] https://github.com/%GHUSER%/fastbootCmds
    echo.
    git log --oneline -n 3
    echo.
)

pause
endlocal
