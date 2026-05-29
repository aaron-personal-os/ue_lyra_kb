@echo off


cd /d "%~dp0"

::: Check if web-app deps installed
if not exist "node_modules" (
    echo   Web-app dependencies not installed. Running setup first...
    call setup.bat
)

::: Check terminal-server deps (dev-only, see ADR-0003)
set TERMINAL_AVAILABLE=1
if not exist "terminal-server\node_modules" (
    echo   terminal-server dependencies not installed.
    echo    Skipping embedded terminal. Run setup.bat to enable it.
    set TERMINAL_AVAILABLE=0
)

::: Best-effort cleanup of stale token file from older versions
if exist ".terminal-token" del /q ".terminal-token"

echo  Starting Lyra Knowledge Base...
echo    http://localhost:4321
if "%TERMINAL_AVAILABLE%"=="1" echo    (embedded terminal: ws://127.0.0.1:4322)
echo.

::: Open browser after delay
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:4321"

::: Start terminal-server in a separate window (auto-closes when astro dev exits)
if "%TERMINAL_AVAILABLE%"=="1" (
    start "lyra-terminal-server" /MIN cmd /c "cd /d "%~dp0terminal-server" && node index.mjs"
)

call pnpm dev

::: Best-effort cleanup
if "%TERMINAL_AVAILABLE%"=="1" (
    taskkill /FI "WINDOWTITLE eq lyra-terminal-server*" /F >nul 2>nul
)
