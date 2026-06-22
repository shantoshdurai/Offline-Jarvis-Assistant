$WshShell = New-Object -comObject WScript.Shell

$TargetPath = "C:\Users\Dog\Downloads\Gemma3-Assistant\venv\Scripts\pythonw.exe"
$Arguments = "gui.py"
$WorkingDirectory = "C:\Users\Dog\Downloads\Gemma3-Assistant"
$IconLocation = "C:\Users\Dog\Downloads\Gemma3-Assistant\venv\Scripts\python.exe,0"

# Update Start Menu Shortcut
$StartMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Jarvis.lnk"
$Shortcut1 = $WshShell.CreateShortcut($StartMenuPath)
$Shortcut1.TargetPath = $TargetPath
$Shortcut1.Arguments = $Arguments
$Shortcut1.WorkingDirectory = $WorkingDirectory
$Shortcut1.IconLocation = $IconLocation
$Shortcut1.Save()

# Update Desktop Shortcut
$DesktopPath = "$env:USERPROFILE\Desktop\Jarvis.lnk"
$Shortcut2 = $WshShell.CreateShortcut($DesktopPath)
$Shortcut2.TargetPath = $TargetPath
$Shortcut2.Arguments = $Arguments
$Shortcut2.WorkingDirectory = $WorkingDirectory
$Shortcut2.IconLocation = $IconLocation
$Shortcut2.Save()

Write-Output "Shortcuts successfully updated to use pythonw.exe bypass!"
