@echo off
echo Restarting LGS...
taskkill /F /IM LCore.exe 2>nul
timeout /T 3 /NOBREAK >nul
start "" "C:\Program Files\Logitech Gaming Software\LCore.exe"
echo Waiting for LGS to start...
timeout /T 8 /NOBREAK >nul
echo Killing old lcdglance...
taskkill /F /IM python3.13.exe 2>nul
taskkill /F /IM python.exe 2>nul
timeout /T 1 /NOBREAK >nul
echo Starting lcdglance v3.0...
start "" /B python -u C:\Users\VersusPc\lcdglance\lcdglance.py
echo Done!