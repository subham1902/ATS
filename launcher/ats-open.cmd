@echo off
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v ATS_RELEASE_ROOT 2^>nul') do set "ATS_RELEASE_ROOT=%%B"
if not defined ATS_RELEASE_ROOT exit /b 1
pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ATS_RELEASE_ROOT%\scripts\ats-open.ps1" %*
