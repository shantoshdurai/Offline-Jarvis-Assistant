param(
    [string]$Action = "enable"
)

$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\JarvisFastAgent.lnk"
$StartMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Jarvis Fast Agent.lnk"
$DesktopPath = "$env:USERPROFILE\Desktop\Jarvis Fast Agent.lnk"

if ($Action -eq "enable") {
    $WshShell = New-Object -comObject WScript.Shell

    # 1. Startup folder shortcut (runs minimized on boot)
    $Shortcut1 = $WshShell.CreateShortcut($StartupPath)
    $Shortcut1.TargetPath = "$PSScriptRoot\fast_jarvis.bat"
    $Shortcut1.Arguments = "--minimized"
    $Shortcut1.WorkingDirectory = "$PSScriptRoot"
    $Shortcut1.WindowStyle = 7
    $Shortcut1.Hotkey = "CTRL+ALT+J"
    $Shortcut1.IconLocation = "shell32.dll,238"
    $Shortcut1.Save()

    # 2. Desktop shortcut
    $Shortcut2 = $WshShell.CreateShortcut($DesktopPath)
    $Shortcut2.TargetPath = "$PSScriptRoot\fast_jarvis.bat"
    $Shortcut2.WorkingDirectory = "$PSScriptRoot"
    $Shortcut2.Hotkey = "CTRL+ALT+J"
    $Shortcut2.IconLocation = "shell32.dll,238"
    $Shortcut2.Save()

    # 3. Start Menu Programs shortcut
    $Shortcut3 = $WshShell.CreateShortcut($StartMenuPath)
    $Shortcut3.TargetPath = "$PSScriptRoot\fast_jarvis.bat"
    $Shortcut3.WorkingDirectory = "$PSScriptRoot"
    $Shortcut3.Hotkey = "CTRL+ALT+J"
    $Shortcut3.IconLocation = "shell32.dll,238"
    $Shortcut3.Save()

    Write-Host "[OK] Jarvis Fast Agent successfully added to Windows Startup, Desktop, and Start Menu!" -ForegroundColor Green
    Write-Host "[OK] Global launch hotkey registered: CTRL+ALT+J" -ForegroundColor Cyan
} elseif ($Action -eq "disable") {
    if (Test-Path $StartupPath) {
        Remove-Item $StartupPath -Force
        Write-Host "[OK] Jarvis Fast Agent removed from Windows Startup." -ForegroundColor Yellow
    } else {
        Write-Host "Jarvis Fast Agent was not present in Windows Startup."
    }
}
