@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PYTHON_CMD=python") else (set "PYTHON_CMD=py -3")
%PYTHON_CMD% monitor.py
if errorlevel 1 echo Monitor failed. Read the message above. Python 3.10 or newer is required.
pause
