# 面试防作弊监控系统 - 后端启动脚本
# PowerShell 版本

$ErrorActionPreference = "Stop"

$BackendEnv = if ($env:BACKEND_CONDA_ENV) { $env:BACKEND_CONDA_ENV } else { "interview" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "面试防作弊监控系统 - 后端服务启动脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 进入后端目录
$BackendPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BackendPath
Write-Host "工作目录: $BackendPath" -ForegroundColor Gray
Write-Host "Conda 环境: $BackendEnv" -ForegroundColor Gray
Write-Host ""

# 检查虚拟环境
Write-Host "[1/4] 检查虚拟环境..." -ForegroundColor Yellow
try {
    $condaEnvs = conda env list 2>$null | Select-String $BackendEnv
    if ($condaEnvs) {
        Write-Host "✓ 虚拟环境已存在" -ForegroundColor Green
    } else {
        Write-Host "✗ 虚拟环境不存在" -ForegroundColor Red
        Write-Host "请先运行: conda create -n $BackendEnv python=3.10" -ForegroundColor Yellow
        pause
        exit 1
    }
} catch {
    Write-Host "✗ Conda 未安装或不在 PATH 中" -ForegroundColor Red
    pause
    exit 1
}

# 检查配置文件
Write-Host ""
Write-Host "[2/4] 检查配置文件..." -ForegroundColor Yellow
if (Test-Path "config.yaml") {
    Write-Host "✓ config.yaml 存在" -ForegroundColor Green
} else {
    Write-Host "✗ config.yaml 不存在" -ForegroundColor Red
    pause
    exit 1
}

# 检查依赖
Write-Host ""
Write-Host "[3/4] 检查依赖..." -ForegroundColor Yellow
$checkDeps = conda run -n $BackendEnv python -c "import flask, flask_socketio, cv2, mediapipe, psutil, yaml" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 所有依赖已安装" -ForegroundColor Green
} else {
    Write-Host "! 部分依赖缺失，正在安装..." -ForegroundColor Yellow
    conda run -n $BackendEnv pip install -r ..\requirements.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ 依赖安装完成" -ForegroundColor Green
    } else {
        Write-Host "✗ 依赖安装失败" -ForegroundColor Red
        pause
        exit 1
    }
}

# 启动服务
Write-Host ""
Write-Host "[4/4] 启动服务..." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "服务地址: http://localhost:5000" -ForegroundColor Green
Write-Host "健康检查: http://localhost:5000/health" -ForegroundColor Green
Write-Host "性能监控: http://localhost:5000/api/performance" -ForegroundColor Green
Write-Host ""
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 启动
conda run -n $BackendEnv python app.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ 服务启动失败" -ForegroundColor Red
    pause
}
