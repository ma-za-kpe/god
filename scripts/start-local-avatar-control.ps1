param(
  [int]$RuntimePort = 8787,
  [int]$ObserverPort = 5173,
  [string]$HostName = "127.0.0.1",
  [string]$OllamaUrl = "http://localhost:11434",
  [string]$OllamaModel = "",
  [int]$OllamaNumCtx = 8192,
  [switch]$RestartOllama
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ObserverDir = Join-Path $RepoRoot "observer"
$ServerScript = Join-Path $RepoRoot "scripts\local_avatar_control_server.py"
$ArtifactDir = Join-Path $RepoRoot "artifacts\local-avatar-control"
New-Item -ItemType Directory -Force -Path $ArtifactDir | Out-Null

if (-not $OllamaModel) {
  $OllamaModel = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "llama3.1:8b" }
}
if ($env:OLLAMA_NUM_CTX) {
  $OllamaNumCtx = [int]$env:OLLAMA_NUM_CTX
}

$Python = (Get-Command python -ErrorAction Stop).Source

function Find-OllamaExe {
  $cmd = Get-Command ollama -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $local = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
  if (Test-Path $local) { return $local }
  throw "ollama.exe not found. Install Ollama or add it to PATH."
}

function Wait-Ollama {
  param([string]$Url, [int]$TimeoutSeconds = 45)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      return Invoke-RestMethod -Uri "$Url/api/tags" -TimeoutSec 5
    } catch {
      Start-Sleep -Seconds 2
    }
  } while ((Get-Date) -lt $deadline)
  throw "Ollama did not become ready at $Url"
}

function Start-LocalOllama {
  param([string]$Url, [string]$Model, [switch]$ForceRestart)
  $ollama = Find-OllamaExe
  $ollamaOut = Join-Path $ArtifactDir "ollama.out.log"
  $ollamaErr = Join-Path $ArtifactDir "ollama.err.log"

  if ($ForceRestart) {
    Get-Process -ErrorAction SilentlyContinue |
      Where-Object { $_.ProcessName -eq "ollama" -and $_.Path -eq $ollama } |
      Stop-Process -Force
    Start-Sleep -Seconds 1
  }

  try {
    $tags = Invoke-RestMethod -Uri "$Url/api/tags" -TimeoutSec 4
  } catch {
    Start-Process `
      -FilePath $ollama `
      -ArgumentList @("serve") `
      -WorkingDirectory $RepoRoot `
      -WindowStyle Hidden `
      -RedirectStandardOutput $ollamaOut `
      -RedirectStandardError $ollamaErr `
      -PassThru | Out-Null
    $tags = Wait-Ollama -Url $Url -TimeoutSeconds 60
  }

  $available = @($tags.models | ForEach-Object { $_.name })
  if ($available -notcontains $Model) {
    throw "Required Ollama model '$Model' is not installed. Available models: $($available -join ', ')"
  }
  if ($Model -eq "llama3.1:8b") {
    Write-Warning "llama3.1:8b is installed and usable, but avatar motion quality should be evaluated with a stronger Qwen 14B/27B model once downloaded."
  }
}

Start-LocalOllama -Url $OllamaUrl -Model $OllamaModel -ForceRestart:$RestartOllama

if (-not (Test-Path (Join-Path $ObserverDir "node_modules"))) {
  Push-Location $ObserverDir
  try {
    npm ci
  } finally {
    Pop-Location
  }
}

$ServerArgs = @(
  $ServerScript,
  "--host", $HostName,
  "--port", [string]$RuntimePort,
  "--ollama-url", $OllamaUrl,
  "--ollama-model", $OllamaModel,
  "--ollama-num-ctx", [string]$OllamaNumCtx
)

$ServerOut = Join-Path $ArtifactDir "server.out.log"
$ServerErr = Join-Path $ArtifactDir "server.err.log"
$Server = Start-Process `
  -FilePath $Python `
  -ArgumentList $ServerArgs `
  -WorkingDirectory $RepoRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $ServerOut `
  -RedirectStandardError $ServerErr `
  -PassThru

try {
  Start-Sleep -Seconds 1
  $RuntimeUrl = "http://${HostName}:${RuntimePort}"
  $ObserverUrl = "http://${HostName}:${ObserverPort}/one?control=1"
  try {
    Invoke-RestMethod -Uri "$RuntimeUrl/health" -TimeoutSec 3 | Out-Null
  } catch {
    Write-Warning "Local avatar control runtime did not answer /health yet. Check $ServerErr"
  }

  $env:VITE_RUNTIME_URL = $RuntimeUrl
  Write-Host "Local avatar control runtime: $RuntimeUrl"
  Write-Host "Observer /one: $ObserverUrl"
  Write-Host "Ollama model: $OllamaModel (num_ctx=$OllamaNumCtx)"
  Write-Host "Logs: $ArtifactDir"

  Push-Location $ObserverDir
  try {
    npm run dev -- --host $HostName --port $ObserverPort
  } finally {
    Pop-Location
  }
} finally {
  if ($Server -and -not $Server.HasExited) {
    Stop-Process -Id $Server.Id -Force
  }
}
