@echo off


setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "PROJECT_ROOT=%SCRIPT_DIR%"

if "%PYTHON%"=="" (
    set "PY_BIN=python"
) else (
    set "PY_BIN=%PYTHON%"
)

where "%PY_BIN%" >nul 2>&1
if errorlevel 1 (
    echo [error] Not Find Python 1>&2
    pause
    exit /b 127
)

"%PY_BIN%" "%PROJECT_ROOT%\ToolsScript\misc_tools\sync_agent_config.py" --project-root "%PROJECT_ROOT%" %*

pause
exit /b %ERRORLEVEL%
