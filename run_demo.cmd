@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "PYTHON_CMD=python") else (set "PYTHON_CMD=py -3")
%PYTHON_CMD% -m unittest discover -s tests -v
if errorlevel 1 goto fail
%PYTHON_CMD% run.py demo
if errorlevel 1 goto fail
start "" "docs\index.html"
exit /b 0
:fail
echo Execution failed. Install Python 3.10 or newer and inspect the error above.
pause
exit /b 1
