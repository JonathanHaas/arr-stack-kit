#!/bin/bash
# Double-click this file. That's it — no typing required.
cd "$(dirname "$0")"

if ! docker info > /dev/null 2>&1; then
  osascript -e 'display alert "Docker Desktop isn'"'"'t open" message "Please open the Docker Desktop app first, wait about a minute for it to fully start, then double-click this file again."'
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i '' "s/^DISABLE_AUTH=.*/DISABLE_AUTH=true/" .env
fi

docker compose up -d --build > /tmp/arr-stack-kit-startup.log 2>&1

sleep 3
open "http://localhost:5500"

osascript -e 'tell application "Terminal" to close (every window whose name contains "start-mac")' > /dev/null 2>&1 &

