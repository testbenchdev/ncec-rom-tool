@echo off
rem コンソールを出さずに起動(動作確認済みの環境向け。エラーは画面に出ません)
rem 初回やトラブル時は NCEC_ROM_Editor.bat(コンソール表示)を使ってください。
cd /d "%~dp0"
where pythonw >nul 2>nul && ( start "" pythonw ncec_editor.py & exit /b )
where python  >nul 2>nul && ( start "" python  ncec_editor.py & exit /b )
where py      >nul 2>nul && ( start "" py -w ncec_editor.py & exit /b )
echo Python not found. Run setup_install.bat first.
pause
