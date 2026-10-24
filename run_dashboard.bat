@echo off
title NYC Re-Rental Alert Dashboard
cd /d "%~dp0"
echo Starting local web dashboard at http://localhost:5050 ...
start http://localhost:5050
python app.py --dashboard
pause
