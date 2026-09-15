Set WshShell = CreateObject("WScript.Shell")
WScript.Sleep 5000
WshShell.Run "pythonw.exe ""C:\Users\VersusPc\lcdglance\launch_detached.py""", 0, False
