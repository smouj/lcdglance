' start_lcdglance.vbs
' Copy this file to your Startup folder.
' Assumes lcdglance folder is at %USERPROFILE%\lcdglance

Set WshShell = CreateObject("WScript.Shell")
WScript.Sleep 5000
lcdPath = WshShell.ExpandEnvironmentStrings("%USERPROFILE%\lcdglance\launch_detached.py")
WshShell.Run "pythonw.exe "" + lcdPath + """, 0, False
