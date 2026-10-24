# uninstall_windows_task.ps1
# Unregisters the Windows Scheduled Task for NYC ReRental Alert Service.

$TaskName = "NYC_ReRental_Alert_Service"
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Task '$TaskName' has been removed." -ForegroundColor Green
