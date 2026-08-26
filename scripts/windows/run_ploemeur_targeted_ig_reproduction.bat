@echo off
setlocal
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\run_ploemeur_targeted_ig_reproduction_external.ps1"
set "exit_code=%ERRORLEVEL%"
if not "%exit_code%"=="0" (
  echo.
  echo The targeted IG benchmark failed. Check the log under:
  echo results\ploemeur_targeted_ig_reproduction\logs
)
exit /b %exit_code%
