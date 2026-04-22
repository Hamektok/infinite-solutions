# Update EVE Character Updates task from every 15 min to every 60 min
$task = Get-ScheduledTask -TaskName "EVE Character Updates"
$trigger = $task.Triggers[0]
$trigger.Repetition.Interval = "PT60M"
Set-ScheduledTask -TaskName "EVE Character Updates" -Trigger $trigger
Write-Host "Task updated to run every 60 minutes." -ForegroundColor Green

# Verify
$updated = Get-ScheduledTask -TaskName "EVE Character Updates"
Write-Host "Repetition interval: $($updated.Triggers[0].Repetition.Interval)"
