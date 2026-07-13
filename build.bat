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
    --add-data "%PROJECT_DIR%src\core\settings.json;core" ^
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

REM 이전 버전이 생성한 외부 설정 파일 제거 — 배포 결과는 EXE 하나만 유지
if exist "%PROJECT_DIR%dist\settings.json" del /q "%PROJECT_DIR%dist\settings.json"

echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo   EXE: dist\XYStageOffset.exe
echo.
pause
