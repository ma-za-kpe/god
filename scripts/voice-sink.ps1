param(
  [string]$RuntimeUrl = "http://localhost:8888",
  [int]$PollSeconds = 2
)

Add-Type -AssemblyName System.Speech | Out-Null

$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$synth.SetOutputToDefaultAudioDevice()
$synth.Volume = 100

function Get-VoiceState {
  try {
    return Invoke-RestMethod -Uri "$RuntimeUrl/voice/state?events_limit=40&messages_limit=24" -Method Get -TimeoutSec 5
  } catch {
    return $null
  }
}

function Get-Rate {
  param([double]$Speed)
  $speed = if ($Speed -gt 0) { $Speed } else { 1.0 }
  $rate = [math]::Round((($speed - 1.0) * 6.0))
  if ($rate -lt -10) { return -10 }
  if ($rate -gt 10) { return 10 }
  return [int]$rate
}

$lastUtteranceId = $null

Write-Host "voice-sink listening on $RuntimeUrl"

while ($true) {
  $state = Get-VoiceState
  if (-not $state -or -not $state.plan) {
    Start-Sleep -Seconds $PollSeconds
    continue
  }

  $playbackMode = [string]$state.playback_mode
  if ($playbackMode -notmatch 'sink') {
    Start-Sleep -Seconds $PollSeconds
    continue
  }

  $plan = $state.plan
  $utteranceId = [string]$plan.utterance_id
  $line = [string]$plan.line

  if ([string]::IsNullOrWhiteSpace($utteranceId) -or [string]::IsNullOrWhiteSpace($line)) {
    Start-Sleep -Seconds $PollSeconds
    continue
  }

  if ($utteranceId -eq $lastUtteranceId) {
    Start-Sleep -Seconds $PollSeconds
    continue
  }

  $lastUtteranceId = $utteranceId

  try {
    $synth.SpeakAsyncCancelAll()
  } catch {}

  $synth.Rate = Get-Rate -Speed ([double]$plan.speed)

  try {
    Write-Host ("[{0}] {1}: {2}" -f $utteranceId, $plan.speaker, $line)
    $synth.Speak($line)
  } catch {
    Write-Warning $_
  }

  Start-Sleep -Seconds $PollSeconds
}
