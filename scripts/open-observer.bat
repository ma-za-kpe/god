@echo off
:: Open the GOD observer in Chrome with GPU sandbox disabled.
:: Fixes: "Sandboxed = yes, BindToCurrentSequence failed" WebGL error
:: when running inside restricted Electron/Chromium previews.
::
:: Usage:
::   scripts\open-observer.bat            → opens /stage (default, OBS overlay)
::   scripts\open-observer.bat stage      → opens /stage (full ensemble)
::   scripts\open-observer.bat classic    → opens /classic (pure-HTML fallback)

setlocal

set MODE=%~1
if "%MODE%"=="" set MODE=one
set URL=http://localhost:3000/%MODE%

:: Find Chrome — check common install paths
set CHROME=
for %%P in (
  "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
  "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
  "%LocalAppData%\Google\Chrome\Application\chrome.exe"
  "%ProgramFiles%\Chromium\Application\chrome.exe"
  "%ProgramFiles(x86)%\Chromium\Application\chrome.exe"
) do (
  if exist %%P (
    if "%CHROME%"=="" set CHROME=%%P
  )
)

if "%CHROME%"=="" (
  echo [open-observer] Chrome not found at default paths.
  echo Open %URL% manually with: --disable-gpu-sandbox --use-angle=swiftshader
  pause
  exit /b 1
)

echo [open-observer] Opening %URL%
echo [open-observer] Chrome: %CHROME%

:: --disable-gpu-sandbox  : allows GPU access from the browser process
:: --use-angle=d3d11      : use Direct3D 11 backend (Windows native GPU)
:: If GPU still fails on this machine, swap d3d11 → swiftshader (software render)
start "" %CHROME% ^
  --disable-gpu-sandbox ^
  --use-angle=d3d11 ^
  --disable-features=IsolateOrigins ^
  --disable-site-isolation-trials ^
  "%URL%"

endlocal
