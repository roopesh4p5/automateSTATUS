@echo off
setlocal enabledelayedexpansion
REM ========================================================
REM Office Network Health Monitor - Windows Task Setup (Batch)
REM Complies with PRD Section 23 & 24
REM ========================================================

set "TASK_NAME=OfficeNetworkHealthMonitor"

REM Resolve absolute path to monitor.py
for %%i in ("%~dp0..") do set "MONITOR_DIR=%%~fi"
set "MONITOR_PATH=%MONITOR_DIR%\monitor.py"

set "INTERVAL_MINUTES=%~1"
if "%INTERVAL_MINUTES%"=="" set "INTERVAL_MINUTES=10"

echo ========================================================
echo  Office Network Health Monitor - Windows Task Setup
echo ========================================================
echo Task Name: %TASK_NAME%
echo Monitor Script: %MONITOR_PATH%
echo Interval: Every %INTERVAL_MINUTES% minutes

REM Find absolute path to pythonw.exe (windowless, headless)
set "PYTHON_PATH="
for /f "delims=" %%i in ('where pythonw 2^>nul') do (
    if not defined PYTHON_PATH set "PYTHON_PATH=%%i"
)
if not defined PYTHON_PATH (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if not defined PYTHON_PATH set "PYTHON_PATH=%%i"
    )
)

if not defined PYTHON_PATH (
    echo Error: Python was not found in PATH.
    pause
    exit /b 1
)

echo Headless Python: %PYTHON_PATH%

REM Check if admin privileges are present
net session >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Running with Administrator privileges.
    REM Admin registration: runs under current user or SYSTEM with highest privileges
    schtasks /Create /SC MINUTE /MO %INTERVAL_MINUTES% /TN "%TASK_NAME%" /TR "\"%PYTHON_PATH%\" \"%MONITOR_PATH%\"" /F /RL HIGHEST
) else (
    echo Running as standard user.
    schtasks /Create /SC MINUTE /MO %INTERVAL_MINUTES% /TN "%TASK_NAME%" /TR "\"%PYTHON_PATH%\" \"%MONITOR_PATH%\"" /F
)

if %ERRORLEVEL% equ 0 (
    echo.
    echo Task '%TASK_NAME%' registered successfully!
    echo It will trigger headlessly every %INTERVAL_MINUTES% minutes in the background.
    echo.
    echo Triggering initial test run now...
    schtasks /Run /TN "%TASK_NAME%"
    echo Check your email inbox in 15 seconds!
) else (
    echo.
    echo Failed to create scheduled task. Error code: %ERRORLEVEL%
)

echo.
pause
