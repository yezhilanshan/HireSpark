[CmdletBinding()]
param(
    [string]$BackendCondaEnv = "interview",
    [string]$TtsCondaEnv = "interview-tts",
    [switch]$SkipFrontend,
    [switch]$StartASR,
    [switch]$SkipASR
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendScript = Join-Path $ScriptRoot "backend\app.py"
$TtsModule = "tts_service.app:app"
$AsrScript = Join-Path $ScriptRoot "live_asr.py"
$FrontendDir = Join-Path $ScriptRoot "frontend"
$DotEnvCandidates = @(
    (Join-Path $ScriptRoot ".env"),
    (Join-Path $ScriptRoot ".env.local")
)

function Get-CondaExecutable {
    $condaFromEnv = $env:CONDA_EXE
    if (-not [string]::IsNullOrWhiteSpace($condaFromEnv) -and (Test-Path -Path $condaFromEnv -PathType Leaf)) {
        return $condaFromEnv
    }

    $condaCommand = Get-Command conda -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $condaCommand) {
        $commonCondaPaths = @(
            (Join-Path $env:USERPROFILE "anaconda3\condabin\conda.bat"),
            (Join-Path $env:USERPROFILE "miniconda3\condabin\conda.bat"),
            (Join-Path $env:ProgramData "anaconda3\condabin\conda.bat"),
            (Join-Path $env:ProgramData "miniconda3\condabin\conda.bat")
        )
        foreach ($candidate in $commonCondaPaths) {
            if (Test-Path -Path $candidate -PathType Leaf) {
                return $candidate
            }
        }
        return $null
    }
    return $condaCommand.Source
}

function Test-CondaEnvExists {
    param(
        [string]$CondaExe,
        [string]$EnvName
    )

    if ([string]::IsNullOrWhiteSpace($CondaExe) -or [string]::IsNullOrWhiteSpace($EnvName)) {
        return $false
    }

    $envLines = & $CondaExe env list 2>$null
    if ($LASTEXITCODE -ne 0 -or $null -eq $envLines) {
        return $false
    }

    $pattern = "^\s*{0}(\s+|$)" -f [regex]::Escape($EnvName)
    foreach ($line in $envLines) {
        if ($line -match $pattern) {
            return $true
        }
    }

    return $false
}

function Import-DotEnvFile {
    param([string]$Path)

    if (-not (Test-Path -Path $Path -PathType Leaf)) {
        return
    }

    $lines = Get-Content -Path $Path -ErrorAction Stop
    foreach ($rawLine in $lines) {
        if ($null -eq $rawLine) {
            $line = ""
        }
        else {
            $line = $rawLine.Trim()
        }
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            continue
        }
        if (-not $line.Contains("=")) {
            continue
        }

        $parts = $line.Split("=", 2)
        if ($parts.Count -gt 0 -and $null -ne $parts[0]) {
            $key = $parts[0].Trim()
        }
        else {
            $key = ""
        }
        if ([string]::IsNullOrWhiteSpace($key)) {
            continue
        }
        if (-not ($key -match "^[A-Za-z_][A-Za-z0-9_]*$")) {
            continue
        }

        if ($parts.Count -gt 1 -and $null -ne $parts[1]) {
            $value = $parts[1].Trim()
        }
        else {
            $value = ""
        }
        if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        elseif ($value.StartsWith("'") -and $value.EndsWith("'") -and $value.Length -ge 2) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ([string]::IsNullOrWhiteSpace($value)) {
            continue
        }
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key, "Process"))) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

function Resolve-DashScopeApiKey {
    foreach ($envFile in $DotEnvCandidates) {
        Import-DotEnvFile -Path $envFile
    }

    $dashKey = [Environment]::GetEnvironmentVariable("DASHSCOPE_API_KEY", "Process")
    $bailianKey = [Environment]::GetEnvironmentVariable("BAILIAN_API_KEY", "Process")

    if ([string]::IsNullOrWhiteSpace($dashKey) -and -not [string]::IsNullOrWhiteSpace($bailianKey)) {
        [Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", $bailianKey, "Process")
        $dashKey = $bailianKey
    }
    elseif ([string]::IsNullOrWhiteSpace($bailianKey) -and -not [string]::IsNullOrWhiteSpace($dashKey)) {
        [Environment]::SetEnvironmentVariable("BAILIAN_API_KEY", $dashKey, "Process")
        $bailianKey = $dashKey
    }

    if (-not [string]::IsNullOrWhiteSpace($dashKey) -or -not [string]::IsNullOrWhiteSpace($bailianKey)) {
        return $true
    }

    $apiKeyFile = [Environment]::GetEnvironmentVariable("DASHSCOPE_API_KEY_FILE_PATH", "Process")
    if ([string]::IsNullOrWhiteSpace($apiKeyFile)) {
        $apiKeyFile = Join-Path $env:USERPROFILE ".dashscope\api_key"
    }
    if (Test-Path -Path $apiKeyFile -PathType Leaf) {
        $fileKey = (Get-Content -Path $apiKeyFile -TotalCount 1 -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($null -eq $fileKey) {
            $fileKey = ""
        }
        else {
            $fileKey = $fileKey.Trim()
        }
        if (-not [string]::IsNullOrWhiteSpace($fileKey)) {
            [Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", $fileKey, "Process")
            [Environment]::SetEnvironmentVariable("BAILIAN_API_KEY", $fileKey, "Process")
            return $true
        }
    }

    return $false
}

function Start-ServiceWindow {
    param(
        [string]$ServiceName,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $safeServiceName = $ServiceName -replace "'", "''"
    $safeWorkingDirectory = $WorkingDirectory -replace "'", "''"

    $bootstrap = @"
`$Host.UI.RawUI.WindowTitle = '职跃星辰 - $safeServiceName'
Set-Location -Path '$safeWorkingDirectory'
Write-Host '[职跃星辰] Starting $safeServiceName ...' -ForegroundColor Cyan
$Command
if (`$LASTEXITCODE -ne 0) {
    Write-Host '[职跃星辰] $safeServiceName exited with code ' `$LASTEXITCODE -ForegroundColor Red
}
"@

    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $bootstrap
    ) | Out-Null
}

function Wait-HttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    Write-Host "[职跃星辰] Waiting for ${Name}: $Url" -ForegroundColor DarkCyan

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "[职跃星辰] $Name is ready." -ForegroundColor Green
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 2
            continue
        }
    }

    Write-Warning "$Name did not become ready within $TimeoutSeconds seconds: $Url"
    return $false
}

function Assert-PortFree {
    param(
        [int]$Port,
        [string]$ServiceName
    )

    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($null -eq $listeners) {
        return
    }

    $pids = @(
        $listeners |
            Where-Object { $_.OwningProcess -gt 0 } |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    $pidText = if ($pids.Count -gt 0) { $pids -join ", " } else { "unknown" }
    throw "$ServiceName port $Port is already in use by process id(s): $pidText. Close the old service window or stop that process before running start_all.ps1 again."
}

if (-not (Test-Path -Path $BackendScript -PathType Leaf)) {
    throw "Backend entry not found: $BackendScript"
}

$startFrontend = -not $SkipFrontend
$startAsr = [bool]$StartASR -and -not $SkipASR

if ($startFrontend -and -not (Test-Path -Path $FrontendDir -PathType Container)) {
    throw "Frontend directory not found: $FrontendDir"
}

if ($startAsr -and -not (Test-Path -Path $AsrScript -PathType Leaf)) {
    Write-Warning "ASR script not found, skip ASR startup: $AsrScript"
    $startAsr = $false
}

$npmCommand = Get-Command npm -ErrorAction SilentlyContinue

$condaExe = Get-CondaExecutable
$backendUseConda = Test-CondaEnvExists -CondaExe $condaExe -EnvName $BackendCondaEnv
$ttsUseConda = Test-CondaEnvExists -CondaExe $condaExe -EnvName $TtsCondaEnv

if ($null -eq $condaExe) {
    throw "Conda not found. Please install Conda and ensure 'conda' is available in PATH."
}

if (-not $backendUseConda) {
    throw "Conda env '$BackendCondaEnv' not found. Backend/ASR startup aborted."
}

if (-not $ttsUseConda) {
    throw "Conda env '$TtsCondaEnv' not found. TTS startup aborted."
}

if ($startFrontend -and $null -eq $npmCommand) {
    throw "npm command not found. Please install Node.js first."
}

Assert-PortFree -Port 5000 -ServiceName "Backend"
Assert-PortFree -Port 5001 -ServiceName "TTS"
if ($startFrontend) {
    Assert-PortFree -Port 3000 -ServiceName "Frontend"
}

$hasDashScopeApiKey = Resolve-DashScopeApiKey
if ($startAsr -and -not $hasDashScopeApiKey) {
    throw "ASR requires DASHSCOPE_API_KEY (or BAILIAN_API_KEY). Please set it in environment variables or .env."
}

Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "职跃星辰 unified startup script" -ForegroundColor Cyan
Write-Host "Project root: $ScriptRoot" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor DarkCyan

$backendCommand = "`$env:SOCKETIO_ASYNC_MODE = 'threading'; & '$condaExe' run -n '$BackendCondaEnv' python '.\backend\app.py'"

$ttsCommand = "& '$condaExe' run -n '$TtsCondaEnv' python -m uvicorn $TtsModule --host 0.0.0.0 --port 5001"

if ($startAsr) {
    $asrCommand = "`$env:BACKEND_URL = 'http://localhost:5000'; if (-not `$env:DASHSCOPE_API_KEY -and `$env:BAILIAN_API_KEY) { `$env:DASHSCOPE_API_KEY = `$env:BAILIAN_API_KEY }; & '$condaExe' run -n '$BackendCondaEnv' python '.\live_asr.py'"
}

$frontendCommand = "Set-Location '.\frontend'; if ((-not (Test-Path '.\node_modules')) -or (-not (Test-Path '.\node_modules\.bin\next.cmd'))) { npm install; if (`$LASTEXITCODE -ne 0) { exit `$LASTEXITCODE } }; npm run dev"

Start-ServiceWindow -ServiceName "Backend" -WorkingDirectory $ScriptRoot -Command $backendCommand
Wait-HttpReady -Name "Backend Socket.IO" -Url "http://127.0.0.1:5000/socket.io/?EIO=4&transport=polling" -TimeoutSeconds 90 | Out-Null

Start-ServiceWindow -ServiceName "TTS" -WorkingDirectory $ScriptRoot -Command $ttsCommand
Wait-HttpReady -Name "TTS" -Url "http://127.0.0.1:5001/health" -TimeoutSeconds 60 | Out-Null

if ($startAsr) {
    Start-ServiceWindow -ServiceName "ASR" -WorkingDirectory $ScriptRoot -Command $asrCommand
}

if ($startFrontend) {
    Start-ServiceWindow -ServiceName "Frontend" -WorkingDirectory $ScriptRoot -Command $frontendCommand
}

Write-Host ""
Write-Host "All requested services have been started in separate PowerShell windows." -ForegroundColor Green
Write-Host "Backend:  http://localhost:5000" -ForegroundColor Gray
Write-Host "TTS:      http://localhost:5001/health" -ForegroundColor Gray
if ($startFrontend) {
    Write-Host "Frontend: http://localhost:3000" -ForegroundColor Gray
}
Write-Host ""
Write-Host "Tips:" -ForegroundColor DarkCyan
Write-Host "1) live_asr.py is no longer started by default; use -StartASR only for the standalone desktop ASR client." -ForegroundColor Gray
Write-Host "2) Use -SkipFrontend to only run backend-side services." -ForegroundColor Gray
