# registers the Windows PTP client against a grandmaster, using Microsoft's documented values
# source: github.com/microsoft/W32Time, Precision Time Protocol, Windows Configuration Helpers

param(
    [string]$masterAddress = "10.0.0.30"
)

$providerPath = "HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\PtpClient"

reg add $providerPath /t REG_SZ /v PtpMasters /d "$masterAddress" /f
reg add $providerPath /t REG_DWORD /v Enabled /d 1 /f
reg add $providerPath /t REG_DWORD /v InputProvider /d 1 /f
reg add $providerPath /t REG_SZ /v DllName /d "c:\windows\system32\ptpprov.dll" /f
reg add $providerPath /t REG_DWORD /v DelayPollInterval /d 0x3e80 /f
reg add $providerPath /t REG_DWORD /v AnnounceInterval /d 0x0fa0 /f

# the PTP provider and the NTP client are both input providers, so Microsoft's helper runs with NTP off
reg add HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient /t REG_DWORD /v Enabled /d 0 /f

if (-not (Get-NetFirewallRule -Name "PTP-319" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "PTP-319" -Name "PTP-319" -LocalPort 319 -Direction Inbound -Action Allow -Protocol UDP | Out-Null
    New-NetFirewallRule -DisplayName "PTP-320" -Name "PTP-320" -LocalPort 320 -Direction Inbound -Action Allow -Protocol UDP | Out-Null
}

Restart-Service w32time
Start-Sleep -Seconds 10
w32tm /resync /force
Start-Sleep -Seconds 5
w32tm /query /status
