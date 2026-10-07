@echo off
REM ========================================================
REM Office Network Health Monitor - Windows Task Setup (Batch)
REM Complies with PRD Section 23 & 24
REM ========================================================

set TASK_NAME=OfficeNetworkHealthMonitor
set SCRIPT_DIR=%~dp0
set MONITOR_DIR=%SCRIPT_DIR%..
set MONITOR_PATH=%MONITOR_DIR%\monitor.py

set INTERVAL_MINUTES=%1
if "%INTERVAL_MINUTES%"=="" set INTERVAL_MINUTES=10

echo Registering headless scheduled task: %TASK_NAME% (every %INTERVAL_MINUTES% minutes)
echo Python script target: %MONITOR_PATH%

REM Detect headless pythonw (windowless Python to prevent terminal window popups)
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PYTHON_EXE=pythonw
    echo Headless Python detected: pythonw
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo Error: Neither pythonw nor python was found in PATH.
        pause
        exit /b 1
    )
    set PYTHON_EXE=python
    echo Warning: pythonw not found in PATH, using python
)

REM Create task to run headlessly every N minutes (default: 10 minutes)
REM Running under SYSTEM (Session 0) + pythonw guarantees zero terminal window popup
schtasks /Create /SC MINUTE /MO %INTERVAL_MINUTES% /TN "%TASK_NAME%" /TR "\"%PYTHON_EXE%\" \"%MONITOR_PATH%\"" /F /RU "SYSTEM"

if %ERRORLEVEL% equ 0 (
    echo.
    echo Successfully registered %TASK_NAME%!
    echo The monitor will run headlessly every %INTERVAL_MINUTES% minutes in the background.
) else (
    echo.
    echo Note: If running as standard user, registering under CURRENT_USER instead:
    schtasks /Create /SC MINUTE /MO %INTERVAL_MINUTES% /TN "%TASK_NAME%" /TR "\"%PYTHON_EXE%\" \"%MONITOR_PATH%\"" /F
    echo Registered task under current user with %PYTHON_EXE% (headless).
)

echo.
echo To run the task immediately in the background for verification:
echo   schtasks /Run /TN "%TASK_NAME%"
echo.
pause
