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
    [string]$PythonPath = "python.exe"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$monitorScript = Join-Path $projectRoot "office-monitor\monitor.py"

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

    # Verify python path
    $resolvedPython = (Get-Command $PythonPath -ErrorAction SilentlyContinue).Source
    if (-not $resolvedPython) {
        $resolvedPython = "python.exe"
    }
    Write-Host "Using Python: $resolvedPython" -ForegroundColor Green

    # Task Action: Run python monitor.py in its working directory
    $workDir = Join-Path $projectRoot "office-monitor"
    $taskAction = New-ScheduledTaskAction -Execute $resolvedPython -Argument "`"$monitorScript`"" -WorkingDirectory $workDir

    # Trigger: Hourly repetition indefinitely (PRD Section 23)
    $taskTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)

    # Settings: Run on AC/battery, wake to run, restart on failure
    $taskSettings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 5)

    # Register task: Run with highest privileges / system context for server room laptop (PRD Section 24)
    try {
        # Check if already exists
        $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Host "Existing task found. Unregistering previous version..." -ForegroundColor Yellow
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }

        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $taskAction `
            -Trigger $taskTrigger `
            -Settings $taskSettings `
            -Description "Hourly Network Health Monitor internal office check"

        Write-Host "`nTask '$TaskName' registered successfully!" -ForegroundColor Green
        Write-Host "Schedule: Runs every 1 hour, even after laptop reboot." -ForegroundColor Green
        Write-Host "To test run immediately, execute: .\setup_task_windows.ps1 -Action RunNow" -ForegroundColor Cyan
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
