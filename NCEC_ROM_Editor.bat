@echo off
chcp 932 >nul
cd /d "%~dp0"
title NCEC ROM Map Editor
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where py >nul 2>nul && set "PY=py" )
if not defined PY (
  echo [エラー] Python が見つかりません。
  echo   python.org から Python をインストールし「Add Python to PATH」を有効にしてください。
  echo   その後 setup_install.bat を一度ダブルクリックしてから起動してください。
  echo.
  pause
  exit /b 1
)
"%PY%" ncec_editor.py
if errorlevel 1 (
  echo.
  echo [エラー終了 code=%errorlevel%] 依存パッケージ未導入の可能性があります。
  echo   setup_install.bat を実行、または次を実行:  pip install -r requirements.txt
  echo   CANアダプタのドライバ設定は docs\SETUP_ja.md 第3節(Zadig で WinUSB)。
  echo.
  pause
)
