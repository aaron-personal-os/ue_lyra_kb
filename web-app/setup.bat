@echo off

setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo   Lyra Knowledge Base  Setup             
echo.

::: Check Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo  Node.js not found!
    echo  Please install Node.js ^>= 18: https://nodejs.org/
    pause
    exit /b 1
)

for /f "tokens=1" %%a in ('node -e "console.log(process.version.split('.')[0].replace('v',''))"') do set NODE_VER=%%a
if !NODE_VER! LSS 18 (
    echo  Node.js ^>= 18 required
    echo    Download: https://nodejs.org/
    pause
    exit /b 1
)
echo  Node.js detected

::: Check/Install pnpm
where pnpm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo  Installing pnpm...
    call npm install -g pnpm
)
echo  pnpm detected

::: Install dependencies
echo.
echo  Installing project dependencies...
call pnpm install

::: Install dev-only terminal-server dependencies (ADR-0003)
echo.
echo  Installing terminal-server dependencies (dev-only)...
pushd terminal-server
call pnpm install
if %ERRORLEVEL% NEQ 0 (
    echo   terminal-server install failed — embedded terminal will be unavailable.
    echo    Knowledge base will still work normally.
)
popd

echo    Setup complete!                        
echo   Run: start.bat                          
pause
