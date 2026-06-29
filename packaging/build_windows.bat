@echo off
REM Build Pagewright for Windows. Produces dist\Pagewright\Pagewright.exe — double-click to run.
REM Run this on a Windows machine (a macOS build cannot produce a .exe).
cd /d "%~dp0\.."

python -m venv .build-venv
call .build-venv\Scripts\activate.bat
python -m pip install -U pip
pip install -e ".[desktop,extract,anthropic,openai]" pyinstaller

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
pyinstaller --clean --noconfirm packaging\pagewright.spec

echo.
echo Built dist\Pagewright\Pagewright.exe
echo Zip the dist\Pagewright folder to distribute. Rendering uses the user's Edge/Chrome.
