param(
    [string]$Action = "enable"
)

$RootDir = $PSScriptRoot
$TargetPath = "$RootDir\venv\Scripts\pythonw.exe"
$Arguments = "fast_agent.py"
$IconLocation = "$RootDir\jarvis_icon.ico"

$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\JarvisFastAgent.lnk"
$StartMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Jarvis Fast Agent.lnk"
$DesktopPath = "$env:USERPROFILE\Desktop\Jarvis Fast Agent.lnk"

if ($Action -eq "enable") {
    $WshShell = New-Object -comObject WScript.Shell

    # 1. Startup folder shortcut (runs silently on Windows boot)
    $Shortcut1 = $WshShell.CreateShortcut($StartupPath)
    $Shortcut1.TargetPath = $TargetPath
    $Shortcut1.Arguments = $Arguments
    $Shortcut1.WorkingDirectory = $RootDir
    $Shortcut1.IconLocation = $IconLocation
    $Shortcut1.Description = "Jarvis AI - Fast Voice Copilot"
    $Shortcut1.Save()

    # 2. Desktop shortcut
    $Shortcut2 = $WshShell.CreateShortcut($DesktopPath)
    $Shortcut2.TargetPath = $TargetPath
    $Shortcut2.Arguments = $Arguments
    $Shortcut2.WorkingDirectory = $RootDir
    $Shortcut2.Hotkey = "CTRL+ALT+J"
    $Shortcut2.IconLocation = $IconLocation
    $Shortcut2.Description = "Jarvis AI - Fast Voice Copilot"
    $Shortcut2.Save()

    # 3. Start Menu Programs shortcut
    $Shortcut3 = $WshShell.CreateShortcut($StartMenuPath)
    $Shortcut3.TargetPath = $TargetPath
    $Shortcut3.Arguments = $Arguments
    $Shortcut3.WorkingDirectory = $RootDir
    $Shortcut3.Hotkey = "CTRL+ALT+J"
    $Shortcut3.IconLocation = $IconLocation
    $Shortcut3.Description = "Jarvis AI - Fast Voice Copilot"
    $Shortcut3.Save()

    Write-Host "[OK] Jarvis Fast Agent successfully configured for Windows Startup, Desktop, and Start Menu!" -ForegroundColor Green
    Write-Host "[OK] Silent background launch with custom Jarvis icon." -ForegroundColor Cyan
} elseif ($Action -eq "disable") {
    if (Test-Path $StartupPath) {
        Remove-Item $StartupPath -Force
        Write-Host "[OK] Jarvis Fast Agent removed from Windows Startup." -ForegroundColor Yellow
    } else {
        Write-Host "Jarvis Fast Agent was not present in Windows Startup."
    }
}
