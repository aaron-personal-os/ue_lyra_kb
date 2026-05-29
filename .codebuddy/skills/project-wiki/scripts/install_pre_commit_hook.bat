@echo off
REM install_pre_commit_hook.bat - install pre-commit-template.sh as .git\hooks\pre-commit.
REM For macOS / Linux use install_pre_commit_hook.sh.
REM
REM Usage:
REM   install_pre_commit_hook.bat                  REM install / upgrade
REM   install_pre_commit_hook.bat --uninstall      REM uninstall
REM   install_pre_commit_hook.bat --check-version  REM print version status
REM
REM Note: Git for Windows ships bash that executes hooks, so .sh hook works fine on Windows.
REM v0.5 (R21): supports HOOK_VERSION self-detection; outdated hooks are auto-upgraded.
REM ASCII-only above this line (chcp not yet effective).

setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\..\.."

pushd "%PROJECT_ROOT%" >nul
set "PROJECT_ROOT=%CD%"
popd >nul

set "TEMPLATE=%SCRIPT_DIR%pre-commit-template.sh"
set "HOOK=%PROJECT_ROOT%\.git\hooks\pre-commit"
set "MARKER=wiki_lint.py --check"

if not exist "%PROJECT_ROOT%\.git" (
    echo [error] 未找到 .git\ 目录: %PROJECT_ROOT% 1>&2
    exit /b 2
)

REM Extract HOOK_VERSION from a file (sets _OUT_VER, "" when not found / file missing).
set "_OUT_VER="
if "%~1"=="" goto :install_flow
if /i "%~1"=="--uninstall" goto :uninstall_flow
if /i "%~1"=="--check-version" goto :checkver_flow

:install_flow
if not exist "%TEMPLATE%" (
    echo [error] template 不存在: %TEMPLATE% 1>&2
    exit /b 2
)
call :get_version "%TEMPLATE%" TEMPLATE_VER
if exist "%HOOK%" (
    findstr /c:"%MARKER%" "%HOOK%" >nul
    if errorlevel 1 (
        echo [error] %HOOK% 已存在且不是本脚本装的 1>&2
        echo         请手动合并；或先 install_pre_commit_hook.bat --uninstall 1>&2
        exit /b 2
    )
    call :get_version "%HOOK%" INSTALLED_VER
    if "!INSTALLED_VER!"=="!TEMPLATE_VER!" (
        echo [install] hook 已是最新版本 ^(!TEMPLATE_VER!^)，无需更新
        exit /b 0
    )
    if "!INSTALLED_VER!"=="" set "INSTALLED_VER=pre-r21"
    echo [install] 检测到旧版 pre-commit hook ^(!INSTALLED_VER! -^> !TEMPLATE_VER!^)，覆盖更新
)
copy /y "%TEMPLATE%" "%HOOK%" >nul
echo [install] OK 已安装 pre-commit hook ^(!TEMPLATE_VER!^) -^> %HOOK%
echo [install]   下次 git commit 会自动跑 wiki_lint --update-cache + --check
echo [install]   v0.5 opt-in autofix^: set WIKI_LINT_AUTOFIX_ASYMM=1 ^& git commit ...
echo [install]   想跳过单次：git commit --no-verify
echo [install]   想卸载：install_pre_commit_hook.bat --uninstall
exit /b 0

:uninstall_flow
if not exist "%HOOK%" (
    echo [install] 没有 pre-commit hook，无需移除
    exit /b 0
)
findstr /c:"%MARKER%" "%HOOK%" >nul
if errorlevel 1 (
    echo [error] %HOOK% 不是本脚本装的，不会动它 1>&2
    exit /b 2
)
del /f /q "%HOOK%"
echo [install] 已移除 pre-commit hook: %HOOK%
exit /b 0

:checkver_flow
if not exist "%HOOK%" (
    echo uninstalled
    exit /b 0
)
findstr /c:"%MARKER%" "%HOOK%" >nul
if errorlevel 1 (
    echo foreign
    exit /b 0
)
call :get_version "%HOOK%" INSTALLED_VER
call :get_version "%TEMPLATE%" TEMPLATE_VER
if "!INSTALLED_VER!"=="!TEMPLATE_VER!" (
    echo current ^(!INSTALLED_VER!^)
    exit /b 0
)
if "!INSTALLED_VER!"=="" set "INSTALLED_VER=pre-r21"
echo outdated ^(installed: !INSTALLED_VER!, latest: !TEMPLATE_VER!^)
exit /b 0

:get_version
REM %1 = file path, %2 = output var name
set "%~2="
for /f "tokens=2 delims=: " %%v in ('findstr /c:"# HOOK_VERSION:" "%~1" 2^>nul') do (
    set "%~2=%%v"
    goto :get_version_done
)
:get_version_done
goto :eof
