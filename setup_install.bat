@echo off
chcp 932 >nul
cd /d "%~dp0"
title NCEC ROM Tool - セットアップ(初回のみ)
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where py >nul 2>nul && set "PY=py" )
if not defined PY (
  echo [エラー] Python が見つかりません。先に python.org から Python をインストールし、
  echo         「Add Python to PATH」を有効にしてください(3.10 以上)。
  echo.
  pause
  exit /b 1
)
echo 依存パッケージをインストールします ...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt
echo.
if errorlevel 1 (
  echo [エラー] インストールに失敗しました。ネット接続や Python を確認してください。
) else (
  echo 完了しました。NCEC_ROM_Editor.bat をダブルクリックで起動できます。
  echo ※ CANアダプタ(SH-C30L)は Zadig で WinUSB ドライバ設定が必要です
  echo    (docs\SETUP_ja.md 第3節)。
)
echo.
pause
