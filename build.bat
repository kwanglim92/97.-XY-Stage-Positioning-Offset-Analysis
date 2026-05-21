@echo off
chcp 65001 >nul 2>&1
REM ====================================================
REM  XY Stage Positioning Offset Analysis - PyInstaller Build
REM  Usage: build.bat
REM ====================================================

set PROJECT_DIR=%~dp0
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo ============================================
echo   XY Stage Offset Analysis - PyInstaller Build
echo ============================================
echo.

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "XYStageOffset" ^
    --distpath dist ^
    --workpath build ^
    --specpath build ^
    --add-data "%PROJECT_DIR%src\assets;src\assets" ^
    --collect-all pspylib ^
    --hidden-import=src.core ^
    --hidden-import=src.ui ^
    --hidden-import=src.charts ^
    src\main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo   EXE: dist\XYStageOffset.exe
echo.
pause
