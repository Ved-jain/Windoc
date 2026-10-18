@echo off
setlocal
echo [WinDoc] Setting up local environment...
cd /d "%~dp0"

if not exist ".venv" (
    echo [WinDoc] Creating Python virtual environment...
    py -3 -m venv .venv
)

echo [WinDoc] Installing dependencies and package...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip install -e .[dev]

if not exist "%USERPROFILE%\.local\bin" (
    mkdir "%USERPROFILE%\.local\bin"
)

echo [WinDoc] Registering global command...
echo @echo off > "%USERPROFILE%\.local\bin\windoc.cmd"
echo "%~dp0.venv\Scripts\windoc.exe" %%* >> "%USERPROFILE%\.local\bin\windoc.cmd"

echo & "%~dp0.venv\Scripts\windoc.exe" @args > "%USERPROFILE%\.local\bin\windoc.ps1"

echo [WinDoc] Installation complete!
echo You can now run 'windoc' from ANY terminal window directly.
windoc info
pause
