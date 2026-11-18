@echo off
rem ============================================================
rem  Launch NCEC ROM Map Editor on WSL2 / socketcan (double-click).
rem  Run tools\setup_ncec_wsl.ps1 once (as Administrator) first.
rem  Then just double-click this file:
rem    auto attach adapter to WSL -> bring up can0 -> launch editor.
rem  See docs/setup_wsl_ja.md for the full guide (Japanese).
rem ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\ncec_wsl_launch.ps1" %*
echo.
echo (press any key to close this window)
pause >nul
