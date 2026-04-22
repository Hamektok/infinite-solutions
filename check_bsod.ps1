# Check for BSOD and system crash events
Write-Host "=== RECENT CRITICAL SYSTEM EVENTS ===" -ForegroundColor Cyan

$events = Get-WinEvent -LogName System -MaxEvents 500 -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -in @(41, 6008, 1001, 7, 51, 52, 55, 57, 129, 1000) } |
    Select-Object -First 15 TimeCreated, Id, LevelDisplayName, @{N='Msg';E={$_.Message.Substring(0, [Math]::Min(300, $_.Message.Length))}}

foreach ($e in $events) {
    Write-Host "`n[$($e.TimeCreated)] EventID=$($e.Id) [$($e.LevelDisplayName)]"
    Write-Host $e.Msg
}

Write-Host "`n=== RECENT MINIDUMP FILES ===" -ForegroundColor Cyan
$dumpPath = "C:\Windows\Minidump"
if (Test-Path $dumpPath) {
    Get-ChildItem $dumpPath -Filter "*.dmp" | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name, LastWriteTime, @{N='SizeMB';E={[Math]::Round($_.Length/1MB,1)}} | Format-Table
} else {
    Write-Host "No minidump folder found."
}

Write-Host "`n=== MEMORY DUMP SETTINGS ===" -ForegroundColor Cyan
$reg = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl"
Write-Host "DumpType: $($reg.CrashDumpEnabled) (1=Complete 2=Kernel 3=Small 7=Automatic)"
Write-Host "AutoReboot: $($reg.AutoReboot)"

Write-Host "`n=== DISK HEALTH (S.M.A.R.T.) ===" -ForegroundColor Cyan
Get-WmiObject -Class Win32_DiskDrive | Select-Object Model, Status, Size | Format-Table

Write-Host "`n=== WINDOWS PROFILE STATUS ===" -ForegroundColor Cyan
Get-WinEvent -LogName Application -MaxEvents 200 -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -in @(1509, 1511, 1515, 1530) } |
    Select-Object -First 5 TimeCreated, Id, @{N='Msg';E={$_.Message.Substring(0, [Math]::Min(250, $_.Message.Length))}} |
    Format-List
