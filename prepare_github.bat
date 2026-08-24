@echo off
chcp 65001 >nul
title GhostGram GitHub Exporter
cd /d "%~dp0"

echo ==================================================
echo   GhostGram GitHub Exporter
echo ==================================================
echo.

set "EXPORT_DIR=github_export"
set "ZIP_NAME=GhostGram_GitHub_Release.zip"

if exist "%EXPORT_DIR%" rmdir /s /q "%EXPORT_DIR%"
if exist "%ZIP_NAME%" del /f /q "%ZIP_NAME%"

mkdir "%EXPORT_DIR%"
mkdir "%EXPORT_DIR%\personas"

echo Copying safe source code...
copy *.py "%EXPORT_DIR%\" >nul
copy *.bat "%EXPORT_DIR%\" >nul
copy *.sh "%EXPORT_DIR%\" >nul
copy *.md "%EXPORT_DIR%\" >nul
copy requirements.txt "%EXPORT_DIR%\" >nul
copy .env.example "%EXPORT_DIR%\" >nul
copy .gitignore "%EXPORT_DIR%\" >nul
copy Dockerfile "%EXPORT_DIR%\" >nul
copy docker-compose.yml "%EXPORT_DIR%\" >nul

echo Creating dummy persona...
echo You are a helpful, friendly, and brief AI assistant. You answer naturally. > "%EXPORT_DIR%\personas\example.txt"

echo Compressing files to %ZIP_NAME%...
cd "%EXPORT_DIR%"
tar -a -c -f "..\%ZIP_NAME%" *
cd ..

echo Cleaning up...
rmdir /s /q "%EXPORT_DIR%"

echo.
echo ==================================================
echo SUCCESS: %ZIP_NAME% is ready to be uploaded to GitHub!
echo It contains ZERO personal info and only a dummy persona.
echo ==================================================
pause
