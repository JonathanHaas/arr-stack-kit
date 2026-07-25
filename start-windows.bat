@echo off
REM Double-click this file. That's it — no typing required.
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  msg * "Docker Desktop isn't open. Please open the Docker Desktop app first, wait about a minute, then double-click this file again."
  exit /b 1
)

if not exist .env (
  copy .env.example .env >nul
  powershell -Command "(gc .env) -replace '^DISABLE_AUTH=.*', 'DISABLE_AUTH=true' | Out-File -encoding ASCII .env"
)

docker compose up -d --build > startup.log 2>&1

timeout /t 3 >nul
start http://localhost:5500
exit
