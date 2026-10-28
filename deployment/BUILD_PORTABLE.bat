@echo off
rem ==========================================================================
rem  SIWES Hub - BUILD_PORTABLE.bat
rem  Builds a self-contained Windows package (dist\SIWES-Hub-Portable.zip) so
rem  the whole project can be copied to another PC and started with
rem  START_APP.bat - no Python installation, no internet connection needed.
rem
rem  Build requirements (build machine only):
rem    * deployment\runtimeCache\python-3.13.2-embed-amd64.zip  (embedded Python)
rem    * .venv\Scripts\python.exe + internet for "pip download" of libraries
rem
rem  The produced package contains:
rem    runtime\python\...   embedded Python 3.13 + Django/DRF libraries
rem    backend\ frontend\   application source (the database is NOT included;
rem    database\            it is created on first start)
rem    deployment\          start/stop scripts (run START_APP.bat to launch)
rem    tests\ documentation\ README.md
rem ==========================================================================
setlocal EnableExtensions
title SIWES Hub - Portable Builder

echo.
echo  ============================================================
echo   SIWES Hub - building the portable Windows package
echo  ============================================================
echo.

set "PROJECT_ROOT=%~dp0.."
set "DIST=%PROJECT_ROOT%\dist"
set "BUILD=%DIST%\SIWES-Hub-Portable"
set "CACHE=%~dp0cache"
set "EMBED_ZIP=%~dp0runtimeCache\python-3.13.2-embed-amd64.zip"

rem --------------------------------------------------------------------------
rem 0. Pre-flight checks
rem --------------------------------------------------------------------------
set "VENV_PY=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo  [ERROR] .venv\Scripts\python.exe not found.
    echo          Build this package on the development machine first.
    pause & exit /b 1
)
if not exist "%EMBED_ZIP%" (
    echo  [ERROR] %EMBED_ZIP% not found.
    pause & exit /b 1
)
echo  [0/6] Pre-flight checks passed.

rem --------------------------------------------------------------------------
rem 1. Fresh output directory (a previous build is replaced completely)
rem --------------------------------------------------------------------------
if exist "%BUILD%" rmdir /s /q "%BUILD%"
if exist "%DIST%\SIWES-Hub-Portable.zip" del /q "%DIST%\SIWES-Hub-Portable.zip"
mkdir "%BUILD%" 2>nul
if not exist "%CACHE%\wheels" mkdir "%CACHE%\wheels"
echo  [1/6] Cleared the previous build output.

rem --------------------------------------------------------------------------
rem 2. Copy the application source into the package
rem    (__pycache__, .venv, dist and zips are excluded automatically)
rem --------------------------------------------------------------------------
robocopy "%PROJECT_ROOT%\backend"    "%BUILD%\backend"    /e /xd __pycache__ >nul
robocopy "%PROJECT_ROOT%\frontend"   "%BUILD%\frontend"   /e /xd __pycache__ >nul
robocopy "%PROJECT_ROOT%\deployment" "%BUILD%\deployment" /e /xf BUILD_PORTABLE.bat /xd cache runtimeCache >nul
if exist "%PROJECT_ROOT%\tests" robocopy "%PROJECT_ROOT%\tests" "%BUILD%\tests" /e /xd __pycache__ /xf debug_check.py >nul
if exist "%PROJECT_ROOT%\documentation" robocopy "%PROJECT_ROOT%\documentation" "%BUILD%\documentation" /e >nul
if exist "%PROJECT_ROOT%\README.md" copy /y "%PROJECT_ROOT%\README.md" "%BUILD%\README.md" >nul
if exist "%PROJECT_ROOT%\API_Documentation.md" copy /y "%PROJECT_ROOT%\API_Documentation.md" "%BUILD%\API_Documentation.md" >nul
if exist "%PROJECT_ROOT%\.env.example" copy /y "%PROJECT_ROOT%\.env.example" "%BUILD%\.env.example" >nul
if exist "%PROJECT_ROOT%\.gitignore" copy /y "%PROJECT_ROOT%\.gitignore" "%BUILD%\.gitignore" >nul
if exist "%PROJECT_ROOT%\design\siwes-hub-ui-reference.png" copy /y "%PROJECT_ROOT%\design\siwes-hub-ui-reference.png" "%BUILD%\siwes-hub-ui-reference.png" >nul
if exist "%PROJECT_ROOT%\database" robocopy "%PROJECT_ROOT%\database" "%BUILD%\database" /e /xd data /xf server.log secret_key.txt db.sqlite3 demo_credentials.txt >nul
mkdir "%BUILD%\database\data" 2>nul
echo  [2/6] Copied backend, frontend, tests, documentation and scripts.

rem --------------------------------------------------------------------------
rem 3. Extract the embedded Python runtime
rem --------------------------------------------------------------------------
powershell -NoProfile -Command "Expand-Archive -LiteralPath '%EMBED_ZIP%' -DestinationPath '%BUILD%\runtime\python' -Force"
if errorlevel 1 (
    echo  [ERROR] Extracting the embedded Python runtime failed.
    pause & exit /b 1
)
echo  [3/6] Extracted the embedded Python 3.13 runtime.

rem --------------------------------------------------------------------------
rem 4. Make the site-packages folder visible to the embedded interpreter and
rem    unpack the pure-Python libraries into it.
rem --------------------------------------------------------------------------
set "PTH=%BUILD%\runtime\python\python313._pth"
(
    echo python313.zip
    echo .
    echo ..\site-packages
    echo ..\..\backend
    echo import site
) > "%PTH%"

echo  [4/6] Downloading packages (Django, DRF and friends)...
"%VENV_PY%" -m pip download Django==5.1 djangorestframework==3.17.2 asgiref==3.12.1 sqlparse==0.6.0 tzdata --dest "%CACHE%\wheels" --only-binary=:all: --quiet
if errorlevel 1 (
    echo  [ERROR] Downloading the packages failed - is there an internet
    echo          connection on this machine?
    pause & exit /b 1
)
for %%W in ("%CACHE%\wheels\*.whl") do (
    copy /y "%%W" "%%~dpnW.zip" >nul
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '%%~dpnW.zip' -DestinationPath '%BUILD%\runtime\site-packages' -Force"
    del /q "%%~dpnW.zip" >nul
)
echo        Packages unpacked into runtime\site-packages.

rem --------------------------------------------------------------------------
rem 5. Self-test: the embedded interpreter must import Django, DRF and SQLite.
rem --------------------------------------------------------------------------
"%BUILD%\runtime\python\python.exe" -c "import sqlite3, django, rest_framework; print(' ', 'sqlite', sqlite3.sqlite_version, '- django', django.get_version())"
if errorlevel 1 (
    echo  [ERROR] The embedded runtime self-test failed.
    pause & exit /b 1
)

rem    Sanity check the app itself with the embedded interpreter.
pushd "%BUILD%\backend"
"%BUILD%\runtime\python\python.exe" "%BUILD%\backend\manage.py" check
popd
if errorlevel 1 (
    echo  [ERROR] "manage.py check" failed inside the portable build.
    pause & exit /b 1
)
echo  [5/6] Runtime and application self-tests passed.

rem    Do not ship the build-time secret key: each installation generates its
rem    own on first start (config/settings.py creates it if missing).
del /q "%BUILD%\database\secret_key.txt" 2>nul

rem --------------------------------------------------------------------------
rem 6. Compress the result
rem --------------------------------------------------------------------------
powershell -NoProfile -Command "Compress-Archive -Path '%BUILD%\*' -DestinationPath '%DIST%\SIWES-Hub-Portable.zip' -Force"
echo  [6/6] Created %DIST%\SIWES-Hub-Portable.zip
echo.
echo  ------------------------------------------------------------
echo   Build finished.
echo.
echo   Folder:  %BUILD%
echo     - start it locally with  deployment\START_APP.bat
echo   Zip:     %DIST%\SIWES-Hub-Portable.zip
echo     - extract anywhere on another Windows machine, then run
echo       START_APP.bat - no Python installation required.
echo.
echo   On first start the package creates its own database; a fresh
echo   copy has no users - the launcher asks for the first
echo   administrator, and students/supervisors register on the
echo   registration page linked from the sign-in screen.
echo  ------------------------------------------------------------
echo.
pause
exit /b 0
