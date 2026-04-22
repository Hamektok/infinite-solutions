Get-WmiObject Win32_PnPSignedDriver | Where-Object { $_.DeviceName -like '*Realtek*' } | Select-Object DeviceName, DriverVersion, DriverDate, InfName | Format-List
