@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" %*
if errorlevel 1 echo Action failed. See the message above.
pause
