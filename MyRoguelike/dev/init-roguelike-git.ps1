<#
.SYNOPSIS
    一键初始化 MyRoguelikeGame 仓库的 git + LFS、写入 .gitattributes / .gitignore / AGENTS.md 并首次提交。

.DESCRIPTION
    在 UE 5.7 中用 Third Person C++ 模板创建工程并关闭编辑器后，
    在 g:\UEProjects 目录下执行本脚本即可完成 git 基础配置。

    执行方式：
        cd g:\UEProjects
        powershell -ExecutionPolicy Bypass -File ue_lyra_kb\MyRoguelike\dev\init-roguelike-git.ps1

.NOTES
    远端 push 需要手动操作（你需要先在 GitHub/Gitea 等建好空仓库）：
        cd g:\UEProjects\MyRoguelikeGame
        git remote add origin <你的远端地址>
        git push -u origin main
#>

$ErrorActionPreference = 'Stop'

# ---- 路径配置 ----
$projectDir = 'g:\UEProjects\MyRoguelikeGame'
$kbDir      = 'g:\UEProjects\ue_lyra_kb'
$lfsTemplate  = Join-Path $kbDir 'MyRoguelike\dev\gitattributes.template'
$agentTemplate = Join-Path $kbDir 'MyRoguelike\dev\AGENTS.md.template'

# ---- 检查工程目录 ----
if (-not (Test-Path $projectDir)) {
    Write-Error "未找到工程目录: $projectDir`n请先在 UE 5.7 中创建 Third Person C++ 工程并保存到该位置。"
    exit 1
}

$uprojectFile = Get-ChildItem -Path $projectDir -Filter '*.uproject' -File | Select-Object -First 1
if (-not $uprojectFile) {
    Write-Error "在 $projectDir 中未找到 .uproject 文件，请确认工程已正确创建。"
    exit 1
}

Write-Host "==> 检测到工程: $($uprojectFile.Name)" -ForegroundColor Cyan

# ---- 写入 .gitattributes（LFS 规则）----
Write-Host "==> 写入 .gitattributes ..." -ForegroundColor Cyan
$gitattributes = @"
# Git LFS 规则 — 在产生任何二进制资产之前已配置

# Unreal 资产
*.uasset filter=lfs diff=lfs merge=lfs -text
*.umap filter=lfs diff=lfs merge=lfs -text
*.ubulk filter=lfs diff=lfs merge=lfs -text
*.uexp filter=lfs diff=lfs merge=lfs -text
*.uptnl filter=lfs diff=lfs merge=lfs -text

# 常见美术资源
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.tga filter=lfs diff=lfs merge=lfs -text
*.psd filter=lfs diff=lfs merge=lfs -text
*.fbx filter=lfs diff=lfs merge=lfs -text
*.obj filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.ogg filter=lfs diff=lfs merge=lfs -text

# 视频
*.mp4 filter=lfs diff=lfs merge=lfs -text
"@
Set-Content -Path (Join-Path $projectDir '.gitattributes') -Value $gitattributes -Encoding UTF8
Write-Host "    .gitattributes 写入完成" -ForegroundColor Green

# ---- 写入 .gitignore（UE 标准规则）----
Write-Host "==> 写入 .gitignore ..." -ForegroundColor Cyan
$gitignore = @"
# Unreal Engine 生成目录
Binaries/
Build/
Intermediate/
Saved/
DerivedDataCache/

# Visual Studio
.vs/
*.VC.db
*.VC.opendb
*.sdf
*.opensdf
*.sln
*.suo
*.user

# JetBrains Rider
.idea/
*.DotSettings.user

# VSCode / Cursor
.vscode/

# macOS
.DS_Store

# Perforce（若迁移时用到）
*.p4ignore
"@
Set-Content -Path (Join-Path $projectDir '.gitignore') -Value $gitignore -Encoding UTF8
Write-Host "    .gitignore 写入完成" -ForegroundColor Green

# ---- 写入 AGENTS.md ----
Write-Host "==> 写入 AGENTS.md ..." -ForegroundColor Cyan
$agentsContent = Get-Content -Raw $agentTemplate
Set-Content -Path (Join-Path $projectDir 'AGENTS.md') -Value $agentsContent -Encoding UTF8
Write-Host "    AGENTS.md 写入完成" -ForegroundColor Green

# ---- git init + LFS ----
Write-Host "==> 初始化 git 仓库 ..." -ForegroundColor Cyan
Push-Location $projectDir
try {
    git init
    git lfs install
    git lfs track "*.uasset" "*.umap" "*.ubulk" "*.uexp" "*.uptnl" `
        "*.png" "*.jpg" "*.jpeg" "*.tga" "*.psd" "*.fbx" "*.obj" `
        "*.wav" "*.mp3" "*.ogg" "*.mp4"

    # ---- 首次提交 ----
    Write-Host "==> 首次提交 ..." -ForegroundColor Cyan
    git add .gitattributes .gitignore AGENTS.md
    git add .
    git commit -m "Initial UE project setup

- Third Person C++ template (UE 5.7)
- Git LFS configured for UE binary assets
- AGENTS.md added for AI cross-repo guidance"

    Write-Host ""
    Write-Host "==> 完成！下一步：推送到远端" -ForegroundColor Green
    Write-Host ""
    Write-Host "    git remote add origin <你的远端地址>" -ForegroundColor Yellow
    Write-Host "    git push -u origin main" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "==> 然后用 Cursor 打开工作区开始开发：" -ForegroundColor Green
    Write-Host "    g:\UEProjects\MyRoguelike.code-workspace" -ForegroundColor Yellow
} finally {
    Pop-Location
}
