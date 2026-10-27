<#
  一键把 fastbootCmds 发布到 GitHub。
  用法（在你自己的 PowerShell 里运行，不要在受限环境里跑）：
      pwsh -File .\publish-fastbootCmds.ps1
      pwsh -File .\publish-fastbootCmds.ps1 -Private
      pwsh -File .\publish-fastbootCmds.ps1 -WithRelease   # 顺便把 exe 传到 Release

  前置条件：
    1. 已安装 Git：winget install --id Git.Git -e
    2. 推荐安装 GitHub CLI：winget install --id GitHub.cli -e，然后 gh auth login
       （没有 gh 也可以，脚本会打印手动步骤）
#>
[CmdletBinding()]
param(
    [string]$RepoName = "fastbootCmds",
    [string]$GitHubUser = "",
    [switch]$Private,
    [switch]$WithRelease,
    [string]$Tag = "v0.1.0"
)

$ErrorActionPreference = "Stop"

$projectDir = Join-Path $PSScriptRoot "fastbootCmds"
if (-not (Test-Path (Join-Path $projectDir "README.md"))) {
    throw "找不到项目目录：$projectDir"
}
Set-Location $projectDir

function Require-Command($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "未找到 $name。$hint"
    }
}

Require-Command git "请先安装：winget install --id Git.Git -e"

# ---------- 1. 本地仓库 ----------
if (-not (Test-Path ".git")) {
    Write-Host "==> git init" -ForegroundColor Cyan
    git init -b main | Out-Null
}

# 身份检查（只提示，不擅自改全局配置）
$name  = git config user.name
$email = git config user.email
if (-not $name -or -not $email) {
    throw @"
尚未配置 Git 身份。请先执行（把值换成你自己的）：
  git config --global user.name  "你的名字"
  git config --global user.email "you@example.com"
"@
}

# ---------- 2. 提交 ----------
Write-Host "==> 暂存文件" -ForegroundColor Cyan
git add -A
$staged = git diff --cached --name-only
if ($staged) {
    Write-Host "将要提交：`n$staged"
    git commit -m "feat: fastbootCmds 初始提交" | Out-Null
    Write-Host "==> 提交完成" -ForegroundColor Green
} else {
    Write-Host "==> 没有新改动需要提交" -ForegroundColor Yellow
}

# 确认 exe 没被误提交（.gitignore 已排除，这里只做兜底检查）
$trackedExe = & git ls-files "fastbootCmds.exe"
if ($trackedExe) {
    Write-Warning "fastbootCmds.exe 已被 Git 跟踪（二进制不建议进仓库）。要移除请执行：git rm --cached fastbootCmds.exe"
}

# ---------- 3. 创建远程仓库并推送 ----------
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"              # 没配 origin 时 git 会写 stderr
& git remote get-url origin *> $null
$hasOrigin = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prev

$hasGh = [bool](Get-Command gh -ErrorAction SilentlyContinue)
$authOk = $false
if ($hasGh) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"          # gh auth status 未登录时会写 stderr
    try { gh auth status *> $null; $authOk = ($LASTEXITCODE -eq 0) } catch { $authOk = $false }
    $ErrorActionPreference = $prev
    if (-not $authOk) {
        Write-Host "==> gh 已安装但未登录；执行 gh auth login 可让脚本自动建仓" -ForegroundColor Yellow
    }
}

$repoUrl = "https://github.com/$GitHubUser/$RepoName.git"

if ($hasGh -and $authOk) {
    $visibility = if ($Private) { "--private" } else { "--public" }
    $desc = "Windows fastboot 客户端：按 USB 物理端口选择设备，支持多设备并行刷写，不依赖 fastboot.exe"

    if ($hasOrigin) {
        Write-Host "==> 已存在 origin，直接推送" -ForegroundColor Cyan
        git push -u origin main
    } else {
        Write-Host "==> gh repo create $RepoName $visibility" -ForegroundColor Cyan
        gh repo create $RepoName $visibility --source=. --remote=origin --push --description $desc
    }

    $url = gh repo view --json url -q .url
    Write-Host "==> 仓库地址：$url" -ForegroundColor Green

    if ($WithRelease) {
        $exe = Join-Path $projectDir "fastbootCmds.exe"
        if (Test-Path $exe) {
            Write-Host "==> 创建 Release $Tag 并上传 exe" -ForegroundColor Cyan
            $prev = $ErrorActionPreference
            $ErrorActionPreference = "Continue"      # tag 已存在时不要中断
            & git tag $Tag 2>$null
            & git push origin $Tag 2>$null
            $ErrorActionPreference = $prev
            gh release create $Tag $exe --title $Tag --notes "首个版本：支持按 hub index 选择设备、多设备并行、raw/sparse 刷写。"
        } else {
            Write-Warning "没有找到 fastbootCmds.exe，跳过 Release（先运行 build.bat 编译）"
        }
    }
}
elseif ($GitHubUser) {
    # 没装 gh，但知道用户名：直接关联远程并 push（认证交给 Git Credential Manager 弹窗）
    Write-Host "==> 远程仓库将指向：$repoUrl" -ForegroundColor Cyan
    Write-Host "    现在请打开 https://github.com/new 创建空仓库 $RepoName" -ForegroundColor Yellow
    Write-Host "    仓库名填 $RepoName，不要勾选 README / .gitignore / license，然后点 Create repository" -ForegroundColor Yellow
    Read-Host "建好后按回车，我继续推送"

    if ($hasOrigin) {
        & git remote set-url origin $repoUrl
    } else {
        & git remote add origin $repoUrl
    }

    & git push -u origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Warning @"
推送失败。逐个排查：
  1. https://github.com/$GitHubUser/$RepoName 能打开吗？打不开说明仓库还没创建
  2. 用户名拼对了吗？https://github.com/$GitHubUser
  3. 认证弹窗没出现的话，先执行：git credential-manager configure
  4. 远程仓库不是空的（勾了 README）？先执行：git pull --rebase origin main
"@
    } else {
        Write-Host "==> 已发布：$repoUrl" -ForegroundColor Green
    }
}
else {
    Write-Host @"

没有检测到 GitHub CLI，也没有提供用户名。请任选一种：

  A. 装 GitHub CLI（之后脚本能全自动建仓）：
       winget install --id GitHub.cli -e
       gh auth login

  B. 手动建仓后推送：
       1) 打开 https://github.com/new ，仓库名 $RepoName ，不要勾 README/.gitignore/License
       2) 执行：
            git remote add origin https://github.com/<你的用户名>/$RepoName.git
            git push -u origin main

  也可以直接带用户名重跑本脚本，省掉手输 URL：
       .\publish-fastbootCmds.ps1 -GitHubUser <你的用户名>
"@ -ForegroundColor Yellow
}

Write-Host "`n完成。当前提交：" -ForegroundColor Green
git log --oneline -n 5
