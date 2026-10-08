$WshShell = New-Object -comObject WScript.Shell

$RootDir = "C:\Users\Dog\Downloads\Gemma3-Assistant"
$TargetPath = "$RootDir\venv\Scripts\pythonw.exe"
$Arguments = "fast_agent.py"
$WorkingDirectory = $RootDir
$IconLocation = "$RootDir\jarvis_icon.ico"

# 1. Start Menu Shortcuts (so searching "Jarvis" or "Jarvis Fast Agent" launches it)
$StartMenuPaths = @(
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Jarvis.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Jarvis Fast Agent.lnk"
)

foreach ($path in $StartMenuPaths) {
    $sc = $WshShell.CreateShortcut($path)
    $sc.TargetPath = $TargetPath
    $sc.Arguments = $Arguments
    $sc.WorkingDirectory = $WorkingDirectory
    $sc.IconLocation = $IconLocation
    $sc.Description = "Jarvis AI - Fast Voice Copilot"
    $sc.Save()
    Write-Host "[OK] Updated: $path" -ForegroundColor Green
}

# 2. Desktop Shortcuts
$DesktopPaths = @(
    "$env:USERPROFILE\Desktop\Jarvis.lnk",
    "$env:USERPROFILE\Desktop\Jarvis Fast Agent.lnk"
)

foreach ($path in $DesktopPaths) {
    $sc = $WshShell.CreateShortcut($path)
    $sc.TargetPath = $TargetPath
    $sc.Arguments = $Arguments
    $sc.WorkingDirectory = $WorkingDirectory
    $sc.IconLocation = $IconLocation
    $sc.Description = "Jarvis AI - Fast Voice Copilot"
    $sc.Save()
    Write-Host "[OK] Updated: $path" -ForegroundColor Green
}

# 3. Startup Shortcut (silent background boot)
$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\JarvisFastAgent.lnk"
$sc = $WshShell.CreateShortcut($StartupPath)
$sc.TargetPath = $TargetPath
$sc.Arguments = $Arguments
$sc.WorkingDirectory = $WorkingDirectory
$sc.IconLocation = $IconLocation
$sc.Description = "Jarvis AI - Fast Voice Copilot"
$sc.Save()
Write-Host "[OK] Updated Startup shortcut: $StartupPath" -ForegroundColor Green

Write-Host "`nAll Jarvis shortcuts successfully updated to launch silently via pythonw with custom Jarvis icon!" -ForegroundColor Cyan
