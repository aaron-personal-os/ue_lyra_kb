@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo  Lyra Knowledge Base  Build  Package    
echo.

:: Check Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo    Node.js not found!
    echo    Please install Node.js ^>= 18: https://nodejs.org/
    echo    Or run setup.bat first.
    pause
    exit /b 1
)

for /f "tokens=1" %%a in ('node -e "console.log(process.version.split('.')[0].replace('v',''))"') do set NODE_VER=%%a
if !NODE_VER! LSS 18 (
    echo  Node.js ^>= 18 required
    pause
    exit /b 1
)
echo  Node.js v!NODE_VER!

:: Check pnpm
where pnpm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo  pnpm not found! Run setup.bat first.
    pause
    exit /b 1
)
echo  pnpm detected

:: Check if dependencies installed
if not exist "node_modules" (
    echo.
    echo  Dependencies not found, running install...
    call pnpm install
    if %ERRORLEVEL% NEQ 0 (
        echo  Install failed!
        pause
        exit /b 1
    )
)

:: Build
echo.
echo  Building static site...
call pnpm build
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Build failed!
    pause
    exit /b 1
)

:: Package into zip
echo.
echo  Packaging dist/ ...

set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%
set OUTPUT_NAME=lyra-kb-%TIMESTAMP%


:: Create a serve script inside dist
echo @echo off > "dist\serve.bat"
echo echo   Lyra Knowledge Base  Local Server       >> "dist\serve.bat"
echo echo. >> "dist\serve.bat"
echo echo Starting server at http://localhost:8080 >> "dist\serve.bat"
echo echo Press Ctrl+C to stop. >> "dist\serve.bat"
echo echo. >> "dist\serve.bat"
echo :: Try python first, then npx >> "dist\serve.bat"
echo where python ^>nul 2^>nul >> "dist\serve.bat"
echo if %%ERRORLEVEL%% EQU 0 ( >> "dist\serve.bat"
echo     start http://localhost:8080 >> "dist\serve.bat"
echo     python -m http.server 8080 >> "dist\serve.bat"
echo ) else ( >> "dist\serve.bat"
echo     where npx ^>nul 2^>nul >> "dist\serve.bat"
echo     if %%ERRORLEVEL%% EQU 0 ( >> "dist\serve.bat"
echo         start http://localhost:8080 >> "dist\serve.bat"
echo         npx --yes serve -s . -l 8080 >> "dist\serve.bat"
echo     ) else ( >> "dist\serve.bat"
echo         echo  Neither Python nor Node.js found. >> "dist\serve.bat"
echo         echo    Please open index.html directly or install Python/Node.js >> "dist\serve.bat"
echo         echo    Python: https://www.python.org/ >> "dist\serve.bat"
echo         pause >> "dist\serve.bat"
echo     ) >> "dist\serve.bat"
echo ) >> "dist\serve.bat"

:: Zip using PowerShell
@REM powershell -NoProfile -Command "Compress-Archive -Path '%~dp0dist\*' -DestinationPath '%OUTPUT_ZIP%' -Force"
@REM if %ERRORLEVEL% NEQ 0 (
@REM     echo  Zip failed!
@REM     pause
@REM     exit /b 1
@REM )

echo   Build  Package complete!               
echo   Usage:                                  
echo   1. Run serve.bat (needs Python or Node) 
echo   2. Or open index.html directly          

pause
