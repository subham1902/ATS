@echo off
pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ATS_RELEASE_ROOT%\scripts\ats-stop.ps1" %*
