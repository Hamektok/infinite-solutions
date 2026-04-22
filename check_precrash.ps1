# Look at events in the 15 minutes before the crash (9:31-9:46 AM today)
$crashTime = [datetime]"2026-03-18 09:46:18"
$windowStart = $crashTime.AddMinutes(-15)

Write-Host "=== SYSTEM EVENTS 9:31-9:46 AM (before crash) ===" -ForegroundColor Cyan
Get-WinEvent -LogName System -MaxEvents 2000 -ErrorAction SilentlyContinue |
    Where-Object { $_.TimeCreated -ge $windowStart -and $_.TimeCreated -le $crashTime } |
    Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, @{N='Msg';E={$_.Message.Substring(0,[Math]::Min(150,$_.Message.Length))}} |
    Format-Table -AutoSize

Write-Host "`n=== APPLICATION EVENTS 9:31-9:46 AM ===" -ForegroundColor Cyan
Get-WinEvent -LogName Application -MaxEvents 2000 -ErrorAction SilentlyContinue |
    Where-Object { $_.TimeCreated -ge $windowStart -and $_.TimeCreated -le $crashTime } |
    Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, @{N='Msg';E={$_.Message.Substring(0,[Math]::Min(150,$_.Message.Length))}} |
    Format-Table -AutoSize

Write-Host "`n=== SCHEDULED TASKS THAT RAN TODAY ===" -ForegroundColor Cyan
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" -MaxEvents 500 -ErrorAction SilentlyContinue |
    Where-Object { $_.TimeCreated -ge (Get-Date).Date -and $_.TimeCreated -le $crashTime -and $_.Id -in @(100, 102, 200, 201) } |
    Select-Object TimeCreated, Id, @{N='Task';E={$_.Message.Substring(0,[Math]::Min(200,$_.Message.Length))}} |
    Format-List

Write-Host "`n=== POWER/SLEEP EVENTS TODAY ===" -ForegroundColor Cyan
Get-WinEvent -LogName System -MaxEvents 500 -ErrorAction SilentlyContinue |
    Where-Object { $_.TimeCreated -ge (Get-Date).Date -and $_.Id -in @(1, 12, 13, 42, 107, 506, 507) } |
    Select-Object TimeCreated, Id, @{N='Msg';E={$_.Message.Substring(0,[Math]::Min(200,$_.Message.Length))}} |
    Format-List
