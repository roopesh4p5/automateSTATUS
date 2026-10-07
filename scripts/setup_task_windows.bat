@echo off
REM ========================================================
REM Office Network Health Monitor - Windows Task Setup (Batch)
REM Complies with PRD Section 23 & 24
REM ========================================================

set TASK_NAME=OfficeNetworkHealthMonitor
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set MONITOR_PATH=%PROJECT_ROOT%\office-monitor\monitor.py

echo Registering hourly scheduled task: %TASK_NAME%
echo Python script target: %MONITOR_PATH%

REM Check if Python is available
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python was not found in PATH. Please install Python and add to PATH.
    pause
    exit /b 1
)

REM Create task to run hourly
schtasks /Create /SC HOURLY /MO 1 /TN "%TASK_NAME%" /TR "python \"%MONITOR_PATH%\"" /F /RU "SYSTEM"

if %ERRORLEVEL% equ 0 (
    echo.
    echo Successfully registered %TASK_NAME%!
    echo The monitor will run every hour automatically on this machine.
) else (
    echo.
    echo Note: If running as standard user, registering under CURRENT_USER instead:
    schtasks /Create /SC HOURLY /MO 1 /TN "%TASK_NAME%" /TR "python \"%MONITOR_PATH%\"" /F
)

echo.
echo To run the task immediately for verification:
echo   schtasks /Run /TN "%TASK_NAME%"
echo.
pause
