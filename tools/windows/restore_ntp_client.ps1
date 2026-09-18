# puts Windows timekeeping back on the NTP client and leaves the PTP provider registered but idle

reg add HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\PtpClient /t REG_DWORD /v Enabled /d 0 /f
reg add HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient /t REG_DWORD /v Enabled /d 1 /f

Restart-Service w32time
Start-Sleep -Seconds 8
w32tm /resync /force
Start-Sleep -Seconds 5
w32tm /query /status
w32tm /query /source
