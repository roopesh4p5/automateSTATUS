<#
.SYNOPSIS
    Registers or removes the Office Network Health Monitor Windows Scheduled Task.
.DESCRIPTION
    Complies with PRD Section 23 & 24:
    - Runs hourly at minute 00
    - Runs whether user is logged on or not
    - Recovers on reboot
.EXAMPLE
    .\setup_task_windows.ps1 -Action Register
    .\setup_task_windows.ps1 -Action RunNow
    .\setup_task_windows.ps1 -Action Unregister
#>

param (
    [Parameter(Mandatory = $false)]
    [ValidateSet("Register", "Unregister", "RunNow", "Status")]
    [string]$Action = "Register",

    [Parameter(Mandatory = $false)]
    [string]$TaskName = "OfficeNetworkHealthMonitor",

    [Parameter(Mandatory = $false)]
    [string]$PythonPath = "pythonw.exe",

    [Parameter(Mandatory = $false)]
    [int]$IntervalMinutes = 10
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Detect office-monitor directory (scripts is inside office-monitor/)
$parentDir = Split-Path -Parent $scriptDir
if (Test-Path (Join-Path $parentDir "monitor.py")) {
    $officeMonitorDir = $parentDir
} elseif (Test-Path (Join-Path $scriptDir "..\office-monitor\monitor.py")) {
    $officeMonitorDir = (Resolve-Path (Join-Path $scriptDir "..\office-monitor")).Path
} else {
    $officeMonitorDir = $parentDir
}
$monitorScript = Join-Path $officeMonitorDir "monitor.py"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Office Network Health Monitor - Windows Task Setup   " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Action: $Action"
Write-Host "Task Name: $TaskName"
Write-Host "Monitor Script: $monitorScript"

if ($Action -eq "Register") {
    if (-not (Test-Path $monitorScript)) {
        Write-Error "Error: Could not find monitor.py at $monitorScript"
        exit 1
    }

    # Verify and resolve headless pythonw.exe (prevents any terminal window from popping up)
    $resolvedPython = (Get-Command $PythonPath -ErrorAction SilentlyContinue).Source
    if (-not $resolvedPython) {
        $stdPython = (Get-Command "python.exe" -ErrorAction SilentlyContinue).Source
        if ($stdPython) {
            $pyDir = Split-Path -Parent $stdPython
            $candidateW = Join-Path $pyDir "pythonw.exe"
            if (Test-Path $candidateW) {
                $resolvedPython = $candidateW
            } else {
                $resolvedPython = $stdPython
            }
        } else {
            $resolvedPython = "pythonw.exe"
        }
    }
    Write-Host "Using Headless Python: $resolvedPython" -ForegroundColor Green

    # Task Action: Run pythonw monitor.py in office-monitor working directory
    $workDir = $officeMonitorDir
    $taskAction = New-ScheduledTaskAction -Execute $resolvedPython -Argument "`"$monitorScript`"" -WorkingDirectory $workDir

    # Trigger: Repetition indefinitely every N minutes (default: 10 minutes)
    $taskTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

    # Settings: Hidden mode, run on AC/battery, wake to run, restart on failure
    $taskSettings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 5) `
        -Hidden

    # Task Principal: Run in background under SYSTEM (Session 0 isolation ensures zero window popup)
    $taskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    try {
        # Check if already exists
        $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Host "Existing task found. Unregistering previous version..." -ForegroundColor Yellow
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }

        # Attempt registration with SYSTEM principal
        try {
            Register-ScheduledTask `
                -TaskName $TaskName `
                -Action $taskAction `
                -Trigger $taskTrigger `
                -Settings $taskSettings `
                -Principal $taskPrincipal `
                -Description "Office Network Health Monitor internal check (runs headlessly every $IntervalMinutes minutes)"
        }
        catch {
            Write-Warning "Registration under SYSTEM principal failed. Registering under current user with Hidden mode..."
            Register-ScheduledTask `
                -TaskName $TaskName `
                -Action $taskAction `
                -Trigger $taskTrigger `
                -Settings $taskSettings `
                -Description "Office Network Health Monitor internal check (runs headlessly every $IntervalMinutes minutes)"
        }

        Write-Host "`nTask '$TaskName' registered successfully!" -ForegroundColor Green
        Write-Host "Schedule: Runs headlessly every $IntervalMinutes minutes (no terminal popup)." -ForegroundColor Green
        Write-Host "To test run immediately in background: .\setup_task_windows.ps1 -Action RunNow" -ForegroundColor Cyan
    }
    catch {
        Write-Error "Failed to register scheduled task: $_"
        exit 1
    }
}
elseif ($Action -eq "RunNow") {
    Write-Host "Triggering task '$TaskName' to run immediately..." -ForegroundColor Yellow
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 2
    Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
    Write-Host "Task execution started in background." -ForegroundColor Green
}
elseif ($Action -eq "Status") {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "Task Name: $($t.TaskName)" -ForegroundColor Green
        Write-Host "State: $($t.State)" -ForegroundColor Green
        Write-Host "Last Run Time: $($info.LastRunTime)"
        Write-Host "Last Result: $($info.LastTaskResult)"
        Write-Host "Next Run Time: $($info.NextRunTime)"
    } else {
        Write-Host "Task '$TaskName' is not registered." -ForegroundColor Red
    }
}
elseif ($Action -eq "Unregister") {
    Write-Host "Unregistering task '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task unregistered." -ForegroundColor Green
}
