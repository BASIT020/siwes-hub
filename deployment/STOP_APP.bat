@echo off
rem ==========================================================================
rem  SIWES Hub - STOP_APP.bat
rem  Stops ONLY the local SIWES Hub development server:
rem    * processes whose command line runs "manage.py runserver" on port 8000
rem    * never touches any other Python or unrelated process.
rem ==========================================================================
setlocal EnableExtensions
title SIWES Hub - Stop

echo.
echo  ============================================================
echo   SIWES Hub - stopping the local demo server
echo  ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$found = $false;" ^
  "$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "$runners  = Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object { $_.CommandLine -match 'manage\.py\s+runserver' } | Select-Object -ExpandProperty ProcessId -Unique;" ^
  "$targets  = @($listener) + @($runners) | Where-Object { $_ } | Select-Object -Unique;" ^
  "foreach ($p in $targets) {" ^
  "  try {$name=(Get-Process -Id $p -ErrorAction Stop).ProcessName} catch {$name='?'};" ^
  "  if ($name -match 'python') {" ^
  "    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue;" ^
  "    Write-Host ('  [OK] Stopped SIWES Hub server (PID ' + $p + ')');" ^
  "    $found = $true;" ^
  "  } else {" ^
  "    Write-Host ('  [SKIP] Port 8000 is used by ' + $name + ' (PID ' + $p + '): not a SIWES Hub process, left untouched.');" ^
  "  }" ^
  "}" ^
  "if (-not $found) { Write-Host '  [OK] No SIWES Hub server is running.' }"

echo.
echo  Done.
pause
exit /b 0
