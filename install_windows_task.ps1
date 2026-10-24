# install_windows_task.ps1
# Registers a Windows Scheduled Task to run the NYC ReRental Alert Service continuously in the background on startup.

$TaskName = "NYC_ReRental_Alert_Service"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonPath = (Get-Command python.exe).Source
$AppScript = Join-Path $ScriptDir "app.py"

Write-Host "Registering Scheduled Task '$TaskName'..." -ForegroundColor Cyan
Write-Host "Python: $PythonPath"
Write-Host "Script: $AppScript"

# Action to execute pythonw.exe (windowless) or python.exe
$PythonWPath = $PythonPath.Replace("python.exe", "pythonw.exe")
$ExeToRun = if (Test-Path $PythonWPath) { $PythonWPath } else { $PythonPath }

$Action = New-ScheduledTaskAction -Execute $ExeToRun -Argument "`"$AppScript`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogon
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Unregister old task if it exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Monitors NYC affordable housing re-rentals and sends instant Telegram & Email alerts."

Write-Host "`nTask '$TaskName' registered successfully!" -ForegroundColor Green
Write-Host "To start the background task immediately, run:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
