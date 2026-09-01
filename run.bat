@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv" (
    echo Creating a virtual environment the first time this runs...
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo Couldn't create a virtual environment. Make sure Python 3
        echo is installed from https://www.python.org/downloads/ and
        echo that "Add python.exe to PATH" was ticked during install.
        echo.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo Checking dependencies (first run takes a minute or two)...
pip install -q -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Dependency install failed - see the pip output above for details.
    echo If a package failed to build from source, it usually means pip
    echo picked a version with no ready-made Windows install for your
    echo Python version. Try upgrading pip first with:
    echo     .venv\Scripts\python.exe -m pip install --upgrade pip
    echo ...then run run.bat again.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting ShortGeek...
python desktop.py

pause
