$task = Get-ScheduledTask -TaskName "EVE Character Updates"
Write-Host "Repetition interval: $($task.Triggers[0].Repetition.Interval)"
