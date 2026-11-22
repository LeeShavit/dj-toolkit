@echo off
rem Double-click to start Setlist ID. The first run downloads everything it needs
rem (into the "app" folder next to this file) - later runs start in a few seconds.
title Setlist ID
cd /d "%~dp0app" || goto failed
set "PYTHONUTF8=1"
set "UV_NO_MODIFY_PATH=1"
set "UV_INSTALL_DIR=%CD%\tools"
set "UV_CACHE_DIR=%CD%\tools\cache"
set "UV_PYTHON_INSTALL_DIR=%CD%\tools\python"

if not exist "%UV_INSTALL_DIR%\uv.exe" (
  echo First-time setup - this takes a minute or two...
  powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex" >nul
  if not exist "%UV_INSTALL_DIR%\uv.exe" (
    echo Setup failed. Check your internet connection and try again.
    goto failed
  )
)
"%UV_INSTALL_DIR%\uv.exe" run --quiet --upgrade-package yt-dlp app.py || goto failed
exit /b 0

:failed
echo.
echo Setlist ID stopped because of an error (see above).
pause
