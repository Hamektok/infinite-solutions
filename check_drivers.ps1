# Check for recently updated/problematic drivers
Write-Host "=== STOP CODE FROM LATEST CRASH ===" -ForegroundColor Cyan
Write-Host "0x000000D1 = DRIVER_IRQL_NOT_LESS_OR_EQUAL (faulty driver)"

Write-Host "`n=== NETWORK ADAPTERS (top suspect for 0xD1) ===" -ForegroundColor Cyan
Get-WmiObject Win32_NetworkAdapter | Where-Object { $_.PhysicalAdapter -eq $true } |
    Select-Object Name, MACAddress, Status | Format-Table

Write-Host "`n=== ALL DRIVERS SORTED BY DATE (newest first) ===" -ForegroundColor Cyan
Get-WmiObject Win32_PnPSignedDriver |
    Where-Object { $_.DriverDate -ne $null } |
    Sort-Object DriverDate -Descending |
    Select-Object -First 20 DeviceName, DriverVersion, DriverDate, Manufacturer |
    Format-Table -AutoSize

Write-Host "`n=== DRIVER ERRORS IN LAST 7 DAYS ===" -ForegroundColor Cyan
$since = (Get-Date).AddDays(-7)
Get-WinEvent -LogName System -MaxEvents 1000 -ErrorAction SilentlyContinue |
    Where-Object { $_.TimeCreated -gt $since -and $_.LevelDisplayName -eq 'Error' -and $_.ProviderName -notmatch 'Microsoft-Windows-Security' } |
    Select-Object -First 10 TimeCreated, Id, ProviderName, @{N='Msg';E={$_.Message.Substring(0,[Math]::Min(200,$_.Message.Length))}} |
    Format-List

Write-Host "`n=== WINDOWS UPDATE HISTORY (recent) ===" -ForegroundColor Cyan
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 Description, HotFixID, InstalledOn | Format-Table
