@echo off
chcp 65001 >nul
REM ============================================================
REM  get_engine_root.bat
REM  CMD 包装器，转发给 PowerShell 脚本 get_engine_root.ps1
REM  用法:
REM    get_engine_root.bat            人类可读输出
REM    get_engine_root.bat --json     JSON 输出（AI 调用）
REM    get_engine_root.bat -UProject "X:\path\Foo.uproject"
REM ============================================================
setlocal
set "SCRIPT_DIR=%~dp0"

REM 兼容 --json -> -Json
set "ARGS="
:parse
if "%~1"=="" goto run
if /I "%~1"=="--json" (
    set "ARGS=%ARGS% -Json"
) else (
    set "ARGS=%ARGS% %1"
)
shift
goto parse

:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%get_engine_root.ps1" %ARGS%
exit /b %ERRORLEVEL%
