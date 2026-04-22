$task = Get-ScheduledTask -TaskName "EVE Character Updates" -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "=== TASK DETAILS ===" -ForegroundColor Cyan
    $task | Format-List *

    Write-Host "`n=== TRIGGERS ===" -ForegroundColor Cyan
    $task.Triggers | Format-List *

    Write-Host "`n=== ACTIONS ===" -ForegroundColor Cyan
    $task.Actions | Format-List *
} else {
    Write-Host "Task not found" -ForegroundColor Red
}
