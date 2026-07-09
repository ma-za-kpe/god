param(
  [string]$OllamaUrl = "http://localhost:11434",
  [string]$OllamaModel = "llama3.1:8b",
  [switch]$NoRuntime,
  [switch]$OpenBrowser,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Set-LocalEnv($Name, $Value) {
  [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

Set-LocalEnv "LLM_PROVIDER" "ollama"
Set-LocalEnv "LLM_MODEL" $OllamaModel
Set-LocalEnv "OLLAMA_BASE_URL" "http://host.docker.internal:11434"
Set-LocalEnv "VOICE_PROVIDER" "kokoro"
Set-LocalEnv "TTS_PROVIDER" "kokoro"
Set-LocalEnv "VOICE_MODEL" "kokoro"
Set-LocalEnv "TTS_MODEL" "kokoro"
Set-LocalEnv "VOICE_DRY_RUN" "true"
Set-LocalEnv "VOICE_SYNTHESIS_ENABLED" "false"
Set-LocalEnv "COMFYUI_ENDPOINT" ""
Set-LocalEnv "TTS_ENDPOINT" ""
Set-LocalEnv "AVATAR_GENESIS_ENABLED" "false"
Set-LocalEnv "AVATAR_EVOLUTION_ENABLED" "false"
Set-LocalEnv "AVATAR_ENABLED" "false"
Set-LocalEnv "OBS_ENABLED" "false"
Set-LocalEnv "BROADCAST_DRY_RUN" "true"
Set-LocalEnv "YOUTUBE_ENABLED" "false"
Set-LocalEnv "TWITCH_ENABLED" "false"
Set-LocalEnv "VITE_OLLAMA_URL" $OllamaUrl
Set-LocalEnv "VITE_OLLAMA_MODEL" $OllamaModel
Set-LocalEnv "VITE_AVATAR_LAB_RENDERER" "talkinghead"
Set-LocalEnv "VITE_TALKINGHEAD_AVATAR_URL" "/assets/avatars/brunette.glb"
Set-LocalEnv "OLLAMA_PROXY_URL" "http://host.docker.internal:11434"

$labUrl = "http://127.0.0.1:3000/avatar-lab?ollama=$([uri]::EscapeDataString('/ollama'))&model=$([uri]::EscapeDataString($OllamaModel))&renderer=talkinghead&auto=1&avatar=$([uri]::EscapeDataString('/assets/avatars/brunette.glb'))"
$services = if ($NoRuntime) { @("observer") } else { @("runtime", "observer") }

Write-Host "Local avatar lab"
Write-Host "  Goal: browser-first continuous LLM-directed avatar control."
Write-Host "  Rule: hard-coded avatar behavior is test fallback only; LLM owns dialogue, camera, mood, gesture, gaze, full-body pose, hair, face, hands/fingers, wardrobe, lighting, stage, and every exposed node."
Write-Host "  Ollama: $OllamaUrl"
Write-Host "  Model:  $OllamaModel"
Write-Host "  URL:    $labUrl"
Write-Host ""

try {
  $ollamaTags = Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -Method Get -TimeoutSec 5
  $modelNames = @($ollamaTags.models | ForEach-Object { $_.name })
  if ($modelNames.Count -gt 0) {
    Write-Host "Ollama reachable. Models: $($modelNames -join ', ')"
  } else {
    Write-Host "Ollama reachable. No local models were listed."
  }
} catch {
  Write-Host "Ollama probe failed: $($_.Exception.Message)"
  Write-Host "The lab will still open, but Auto/Ollama intent needs Ollama reachable from the browser."
}

Write-Host ""
Write-Host "Compose services: $($services -join ', ')"
Write-Host "Fish, ComfyUI, OBS, Vast, YouTube, and Twitch profiles are not started by this script."

if ($DryRun) {
  Write-Host "Dry run complete. No Docker command executed."
  exit 0
}

$composeArgs = @("compose", "--profile", "observer", "up", "-d") + $services
& docker @composeArgs

if ($LASTEXITCODE -ne 0) {
  throw "docker compose failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Started. Open: $labUrl"

if ($OpenBrowser) {
  Write-Host "Closing existing Chrome processes before opening the lab."
  Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Milliseconds 700
  $profile = Join-Path $repoRoot "artifacts/chrome-avatar-lab-debug-profile"
  New-Item -ItemType Directory -Force -Path $profile | Out-Null
  Start-Process "chrome.exe" -ArgumentList @(
    "--remote-debugging-port=9222",
    "--user-data-dir=$profile",
    "--autoplay-policy=no-user-gesture-required",
    "--new-window",
    $labUrl
  )
}
