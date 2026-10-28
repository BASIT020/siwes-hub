@echo off
rem ==========================================================================
rem  SIWES Hub - START_APP.bat
rem  Starts the local SIWES Hub server (Django + SQLite) and opens the app
rem  in the default browser. Safe to run repeatedly: it never starts a second
rem  server copy and it never loses data.
rem ==========================================================================
setlocal EnableExtensions
title SIWES Hub - Launcher

echo.
echo  ============================================================
echo   SIWES Hub - starting the local development server
echo  ============================================================
echo.

rem --------------------------------------------------------------------------
rem 1. Locate a usable Python interpreter.
rem    * Portable bundle first:  runtime\python\python.exe
rem    * Project virtual env:    .venv\Scripts\python.exe
rem    * Any system Python:      where python / where py
rem --------------------------------------------------------------------------
set "PROJECT_ROOT=%~dp0.."
set "PY_EXE="

if exist "%PROJECT_ROOT%\runtime\python\python.exe" set "PY_EXE=%PROJECT_ROOT%\runtime\python\python.exe"
if not defined PY_EXE if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" set "PY_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not defined PY_EXE for /f "delims=" %%I in ('where python 2^>nul') do (
    if not defined PY_EXE if exist "%%I" set "PY_EXE=%%I"
)
if not defined PY_EXE for /f "delims=" %%I in ('where py 2^>nul') do (
    if not defined PY_EXE set "PY_EXE=%%I"
)
if not defined PY_EXE (
    echo  [ERROR] No Python interpreter was found.
    echo          Install Python 3.13 or run BUILD_PORTABLE.bat once on a
    echo          machine that has Python, then use the portable build.
    echo.
    pause
    exit /b 1
)
echo  [1/4] Using Python: %PY_EXE%

rem --------------------------------------------------------------------------
rem 2. If the application is already running on port 8000, do NOT start a
rem    second copy - just open the browser again.
rem --------------------------------------------------------------------------
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($c) { exit 0 } else { exit 1 }"
if "%ERRORLEVEL%"=="0" (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/pages/landing.html' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        echo  [2/4] SIWES Hub is already running on port 8000 - reusing it.
        goto open_browser
    )
    echo  [ERROR] Port 8000 is used by another program ^(not SIWES Hub^).
    echo          Stop that program or change the port, then try again.
    echo.
    pause
    exit /b 1
)
echo  [2/4] Port 8000 is free - starting a fresh server.

rem --------------------------------------------------------------------------
rem 3. Apply database migrations (idempotent) and, when the database has no
rem    administrator yet, ask ONCE for the first admin credentials. No demo
rem    users are created automatically; students and supervisors register
rem    themselves on the registration page.
rem --------------------------------------------------------------------------
pushd "%PROJECT_ROOT%\backend"

echo  [3/4] Checking database migrations ^(this is quick when up to date^)...
"%PY_EXE%" manage.py migrate --noinput
if errorlevel 1 (
    echo  [ERROR] Database migration failed - see the messages above.
    popd
    pause
    exit /b 1
)

rem    Creates the first administrator interactively (hidden password) IF no
rem    administrator exists yet. If one already exists it finishes silently.
"%PY_EXE%" manage.py bootstrap_admin
if errorlevel 1 (
    echo  [ERROR] Creating the administrator account failed - see the messages above.
    popd
    pause
    exit /b 1
)

rem    Start the server in its own minimized window; log to a file the user
rem    can inspect later.
echo            Starting server on http://127.0.0.1:8000 ...
start "SIWES Hub Server" /min cmd /c ""%PY_EXE%" manage.py runserver 127.0.0.1:8000 --noreload > "%PROJECT_ROOT%\database\server.log" 2>&1"
popd

rem --------------------------------------------------------------------------
rem 4. Wait until the server answers (max ~30 seconds), then open the browser.
rem --------------------------------------------------------------------------
echo  [4/4] Waiting for the server to answer...
powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(30); while ((Get-Date) -lt $deadline) { try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/pages/landing.html' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } } catch { }; Start-Sleep -Seconds 2 }; exit 1" >nul 2>&1

:open_browser
if errorlevel 1 (
    echo  [WARN] The server did not answer within 30 seconds.
    echo         Check database\server.log for error messages, then try again.
    echo.
    pause
    exit /b 1
)
echo  [4/4] SIWES Hub is running - opening the browser...
start "" "http://127.0.0.1:8000/pages/landing.html"

echo.
echo  ------------------------------------------------------------
echo   The SIWES Hub window is now open in your browser.
echo   Students and supervisors can create their own accounts on
echo   the registration page linked from the sign-in screen.
echo   To stop the server:   stop_app.bat
echo  ------------------------------------------------------------
echo.
powershell -NoProfile -Command "Start-Sleep -Seconds 6" >nul 2>&1
exit /b 0
