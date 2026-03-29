# 面试防作弊监控系统 - 完整启动脚本
# 同时启动后端、独立 TTS 服务和前端

$ErrorActionPreference = "Continue"

function Get-EnvFileValue {
    param(
        [string]$FilePath,
        [string]$Key
    )

    if (-not (Test-Path $FilePath)) {
        return $null
    }

    $line = Get-Content $FilePath |
        Where-Object { $_ -match "^\s*$Key\s*=" } |
        Select-Object -First 1

    if (-not $line) {
        return $null
    }

    return (($line -split "=", 2)[1]).Trim().Trim('"')
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "面试防作弊监控系统 - 完整启动脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$RootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPath = Join-Path $RootPath "backend"
$FrontendPath = Join-Path $RootPath "frontend"
$TtsServiceScript = Join-Path $RootPath "tts_service\\start_tts_service.ps1"
$EnvFilePath = Join-Path $RootPath ".env"

$BackendEnv = if ($env:BACKEND_CONDA_ENV) {
    $env:BACKEND_CONDA_ENV
} else {
    Get-EnvFileValue -FilePath $EnvFilePath -Key "BACKEND_CONDA_ENV"
}
if (-not $BackendEnv) {
    $BackendEnv = "interview"
}

$TtsEnv = if ($env:TTS_CONDA_ENV) {
    $env:TTS_CONDA_ENV
} else {
    Get-EnvFileValue -FilePath $EnvFilePath -Key "TTS_CONDA_ENV"
}
if (-not $TtsEnv) {
    $TtsEnv = "interview-tts"
}

$TtsProvider = if ($env:TTS_PROVIDER) {
    $env:TTS_PROVIDER
} else {
    Get-EnvFileValue -FilePath $EnvFilePath -Key "TTS_PROVIDER"
}
if (-not $TtsProvider) {
    $TtsProvider = "auto"
}

$TtsPort = if ($env:TTS_SERVICE_PORT) {
    $env:TTS_SERVICE_PORT
} else {
    Get-EnvFileValue -FilePath $EnvFilePath -Key "TTS_SERVICE_PORT"
}
if (-not $TtsPort) {
    $TtsPort = "5001"
}

Write-Host "当前工作目录: $RootPath" -ForegroundColor Gray
Write-Host "后端目录: $BackendPath" -ForegroundColor Gray
Write-Host "前端目录: $FrontendPath" -ForegroundColor Gray
Write-Host "TTS 脚本: $TtsServiceScript" -ForegroundColor Gray
Write-Host "后端环境: $BackendEnv" -ForegroundColor Gray
Write-Host "TTS 环境: $TtsEnv" -ForegroundColor Gray
Write-Host "TTS Provider: $TtsProvider" -ForegroundColor Gray
Write-Host "TTS 端口: $TtsPort" -ForegroundColor Gray
Write-Host ""

# 检查路径
if (-not (Test-Path $BackendPath)) {
    Write-Host "✗ 后端目录不存在: $BackendPath" -ForegroundColor Red
    Write-Host "请确保在项目根目录运行此脚本" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "按任意键退出..." -ForegroundColor Gray
    pause
    exit 1
}

if (-not (Test-Path $FrontendPath)) {
    Write-Host "✗ 前端目录不存在: $FrontendPath" -ForegroundColor Red
    Write-Host "请确保在项目根目录运行此脚本" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "按任意键退出..." -ForegroundColor Gray
    pause
    exit 1
}

# 检查虚拟环境
Write-Host "[0/4] 检查环境..." -ForegroundColor Yellow
try {
    $condaCheck = conda --version 2>&1
    Write-Host "✓ Conda 已安装: $condaCheck" -ForegroundColor Green

    $backendEnvCheck = conda env list 2>&1 | Select-String $BackendEnv
    if ($backendEnvCheck) {
        Write-Host "✓ 后端虚拟环境 $BackendEnv 已存在" -ForegroundColor Green
    } else {
        Write-Host "✗ 后端虚拟环境不存在: $BackendEnv" -ForegroundColor Red
        Write-Host "请先运行: conda create -n $BackendEnv python=3.10" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "按任意键退出..." -ForegroundColor Gray
        pause
        exit 1
    }

    $ttsEnvCheck = conda env list 2>&1 | Select-String $TtsEnv
    if ($ttsEnvCheck) {
        Write-Host "✓ TTS 虚拟环境 $TtsEnv 已存在" -ForegroundColor Green
    } else {
        Write-Host "✗ TTS 虚拟环境不存在: $TtsEnv" -ForegroundColor Red
        Write-Host "请先运行: conda create -n $TtsEnv python=3.10" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "按任意键退出..." -ForegroundColor Gray
        pause
        exit 1
    }
} catch {
    Write-Host "✗ Conda 未安装或不在 PATH 中" -ForegroundColor Red
    Write-Host "错误信息: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "按任意键退出..." -ForegroundColor Gray
    pause
    exit 1
}

Write-Host ""

# 启动 TTS
Write-Host "[1/4] 启动独立 TTS 服务..." -ForegroundColor Yellow
if (Test-Path $TtsServiceScript) {
    try {
        $env:TTS_CONDA_ENV = $TtsEnv
        $env:TTS_PROVIDER = $TtsProvider
        $env:TTS_SERVICE_PORT = $TtsPort
        Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$TtsServiceScript`"" -WorkingDirectory $RootPath
        Write-Host "✓ TTS 服务已在新窗口启动" -ForegroundColor Green
    } catch {
        Write-Host "✗ TTS 服务启动失败: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "按任意键退出..." -ForegroundColor Gray
        pause
        exit 1
    }
} else {
    Write-Host "! 未找到 TTS 启动脚本，跳过独立 TTS 服务" -ForegroundColor Yellow
}

Write-Host "等待 TTS 服务初始化..." -ForegroundColor Gray
Start-Sleep -Seconds 2

# 启动后端
Write-Host "[2/4] 启动后端服务..." -ForegroundColor Yellow

$backendScript = Join-Path $BackendPath "start_backend.ps1"
if (Test-Path $backendScript) {
    Write-Host "使用脚本: $backendScript" -ForegroundColor Gray
    try {
        $env:BACKEND_CONDA_ENV = $BackendEnv
        Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$backendScript`"" -WorkingDirectory $BackendPath
        Write-Host "✓ 后端服务已在新窗口启动" -ForegroundColor Green
    } catch {
        Write-Host "✗ 后端启动失败: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "按任意键退出..." -ForegroundColor Gray
        pause
        exit 1
    }
} else {
    Write-Host "! 脚本不存在，使用默认启动方式" -ForegroundColor Yellow
    try {
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:BACKEND_CONDA_ENV='$BackendEnv'; cd '$BackendPath'; conda run -n $BackendEnv python app.py" -WorkingDirectory $BackendPath
        Write-Host "✓ 后端服务已在新窗口启动" -ForegroundColor Green
    } catch {
        Write-Host "✗ 后端启动失败: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "按任意键退出..." -ForegroundColor Gray
        pause
        exit 1
    }
}

Write-Host "等待后端服务初始化..." -ForegroundColor Gray
Start-Sleep -Seconds 3

# 启动前端
Write-Host ""
Write-Host "[3/4] 启动前端服务..." -ForegroundColor Yellow

# 检查 Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "✓ Node.js 已安装: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Node.js 未安装或不在 PATH 中" -ForegroundColor Red
    Write-Host "请从 https://nodejs.org/ 下载安装 Node.js" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "按任意键继续（仅启动后端）..." -ForegroundColor Gray
    pause
    exit 0
}

# 检查 node_modules
$nodeModulesPath = Join-Path $FrontendPath "node_modules"
if (-not (Test-Path $nodeModulesPath)) {
    Write-Host "! 首次运行，正在安装前端依赖..." -ForegroundColor Yellow
    Write-Host "这可能需要几分钟时间，请耐心等待..." -ForegroundColor Gray
    Set-Location $FrontendPath
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 前端依赖安装失败" -ForegroundColor Red
        Write-Host "请手动运行: cd frontend && npm install" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "按任意键继续（仅启动后端）..." -ForegroundColor Gray
        pause
        exit 0
    }
Write-Host "✓ 前端依赖安装完成" -ForegroundColor Green
}

try {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendPath'; npm run dev" -WorkingDirectory $FrontendPath
    Write-Host "✓ 前端服务已在新窗口启动" -ForegroundColor Green
} catch {
    Write-Host "✗ 前端启动失败: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "按任意键继续..." -ForegroundColor Gray
    pause
}

Write-Host ""
Write-Host "[4/4] 启动完成！" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "启动成功！" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "服务地址:" -ForegroundColor Cyan
Write-Host "  TTS 服务: http://localhost:$TtsPort" -ForegroundColor Green
Write-Host "  后端 API: http://localhost:5000" -ForegroundColor Green
Write-Host "  前端界面: http://localhost:3000" -ForegroundColor Green
Write-Host "  TTS 健康检查: http://localhost:$TtsPort/health" -ForegroundColor Green
Write-Host "  健康检查: http://localhost:5000/health" -ForegroundColor Green
Write-Host ""
Write-Host "提示:" -ForegroundColor Cyan
Write-Host "  - 请等待几秒钟让服务完全启动" -ForegroundColor Gray
Write-Host "  - 如果浏览器没有自动打开，请手动访问: http://localhost:3000" -ForegroundColor Gray
Write-Host "  - 关闭对应的窗口可以停止服务" -ForegroundColor Gray
Write-Host "  - TTS、后端和前端运行在各自的窗口中" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "正在等待服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 尝试在浏览器中打开
Write-Host "正在浏览器中打开前端界面..." -ForegroundColor Yellow
try {
    Start-Process "http://localhost:3000"
    Write-Host "✓ 浏览器已打开" -ForegroundColor Green
} catch {
    Write-Host "! 无法自动打开浏览器，请手动访问: http://localhost:3000" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "按任意键退出本窗口（服务会继续在其他窗口运行）..." -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
pause
