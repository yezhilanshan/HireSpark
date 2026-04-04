# 独立 TTS 服务启动脚本

$ErrorActionPreference = "Stop"
$env:CONDA_NO_PLUGINS = "true"
$env:CONDA_REPORT_ERRORS = "false"

function Ensure-HomeEnv {
    $userProfile = $env:USERPROFILE
    if (-not $userProfile) {
        $userProfile = [Environment]::GetFolderPath('UserProfile')
    }
    if (-not $userProfile -or -not (Test-Path $userProfile)) {
        if ($env:USERNAME -and (Test-Path "C:\Users\$($env:USERNAME)")) {
            $userProfile = "C:\Users\$($env:USERNAME)"
        } else {
            $userProfile = "C:\Users\Public"
        }
    }

    $env:USERPROFILE = $userProfile
    $env:HOME = $userProfile
    $homeRoot = [System.IO.Path]::GetPathRoot($userProfile)
    if (-not $homeRoot) {
        $homeRoot = "C:\"
    }
    $env:HOMEDRIVE = $homeRoot.TrimEnd('\')
    $env:HOMEPATH = $userProfile.Substring($env:HOMEDRIVE.Length)
}

Ensure-HomeEnv

$RootPath = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ServicePath = Join-Path $RootPath "tts_service"
$TtsEnv = if ($env:TTS_CONDA_ENV) { $env:TTS_CONDA_ENV } else { "interview-tts" }
$Provider = if ($env:TTS_PROVIDER) { $env:TTS_PROVIDER } else { "auto" }
$Port = if ($env:TTS_SERVICE_PORT) { $env:TTS_SERVICE_PORT } else { "5001" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "独立 TTS 服务启动脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "工作目录: $ServicePath" -ForegroundColor Gray
Write-Host "Conda 环境: $TtsEnv" -ForegroundColor Gray
Write-Host "TTS Provider: $Provider" -ForegroundColor Gray
Write-Host "服务端口: $Port" -ForegroundColor Gray
Write-Host ""

Set-Location $RootPath

try {
    $condaEnvs = conda --no-plugins env list 2>$null | Select-String $TtsEnv
    if (-not $condaEnvs) {
        Write-Host "✗ 虚拟环境不存在: $TtsEnv" -ForegroundColor Red
        Write-Host "请先创建环境，例如: conda create -n $TtsEnv python=3.10" -ForegroundColor Yellow
        pause
        exit 1
    }
} catch {
    Write-Host "✗ Conda 未安装或不在 PATH 中" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[1/2] 检查 TTS 依赖..." -ForegroundColor Yellow
$ImportCheck = if ($Provider -eq "melo" -or $Provider -eq "auto") {
    "import fastapi, uvicorn, edge_tts; import melo"
} else {
    "import fastapi, uvicorn, edge_tts"
}
conda --no-plugins run -n $TtsEnv python -c $ImportCheck *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "! 依赖缺失，开始安装 requirements.txt" -ForegroundColor Yellow
    conda --no-plugins run -n $TtsEnv pip install -r "requirements.txt"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ TTS 依赖安装失败" -ForegroundColor Red
        pause
        exit 1
    }
}

Write-Host "[2/2] 启动 TTS 服务..." -ForegroundColor Yellow
Write-Host "服务地址: http://localhost:$Port" -ForegroundColor Green
Write-Host "健康检查: http://localhost:$Port/health" -ForegroundColor Green
Write-Host ""

conda --no-plugins run -n $TtsEnv python -m uvicorn tts_service.app:app --host 0.0.0.0 --port $Port
