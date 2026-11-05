@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PYTHON_CMD=python") else (set "PYTHON_CMD=py -3")
%PYTHON_CMD% stock_monitor.py
if errorlevel 1 echo Stock monitor failed. Read the error above. See STOCKS.md for setup.
pause
