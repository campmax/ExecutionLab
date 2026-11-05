@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PYTHON_CMD=python") else (set "PYTHON_CMD=py -3")
%PYTHON_CMD% start.py
if errorlevel 1 (
  echo Could not start. Install Python 3.10 or newer with the Python launcher or PATH option.
  pause
)
