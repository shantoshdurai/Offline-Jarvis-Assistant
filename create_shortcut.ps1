$WshShell = New-Object -comObject WScript.Shell
$StartMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Jarvis.lnk"
$Shortcut1 = $WshShell.CreateShortcut($StartMenuPath)
$Shortcut1.TargetPath = "C:\Users\Dog\Downloads\Gemma3-Assistant\jarvis.bat"
$Shortcut1.WorkingDirectory = "C:\Users\Dog\Downloads\Gemma3-Assistant"
$Shortcut1.IconLocation = "cmd.exe"
$Shortcut1.Save()

$DesktopPath = "$env:USERPROFILE\Desktop\Jarvis.lnk"
$Shortcut2 = $WshShell.CreateShortcut($DesktopPath)
$Shortcut2.TargetPath = "C:\Users\Dog\Downloads\Gemma3-Assistant\jarvis.bat"
$Shortcut2.WorkingDirectory = "C:\Users\Dog\Downloads\Gemma3-Assistant"
$Shortcut2.IconLocation = "cmd.exe"
$Shortcut2.Save()

Write-Output "Shortcuts created successfully."
