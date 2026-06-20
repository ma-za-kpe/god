@echo off
set "IMAGE=god-vastai-cli:latest"

rem Build the helper image once if it is not already present.
docker image inspect %IMAGE% >nul 2>nul || docker build -t %IMAGE% -f "%~dp0vastai-cli.Dockerfile" "%~dp0.."

rem Run the downloaded vastai script with persisted config and no repeat pip install.
docker run --rm ^
  -v "%~dp0..\vastai:/vastai" ^
  -v "%USERPROFILE%\.config\vastai:/root/.config/vastai" ^
  -v "%USERPROFILE%\.ssh:/root/.ssh:ro" ^
  %IMAGE% ^
  python /vastai %*
