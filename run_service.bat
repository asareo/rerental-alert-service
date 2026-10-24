@echo off
title NYC Re-Rental Alert Service
cd /d "%~dp0"
echo ========================================================
echo   NYC Affordable Housing Re-Rental Alert Service
echo ========================================================
echo.
python app.py
pause
