#!/usr/bin/env bash
# Install the developer-channel units for the checkout this script lives in, then start the app and the timer.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UNITS="$HOME/.config/systemd/user"
mkdir -p "$UNITS"
for f in pravrudhi-app.service pravrudhi-update.service pravrudhi-update.timer; do
  sed "s#@ROOT@#$ROOT#g" "$ROOT/deploy/systemd/$f" > "$UNITS/$f"
done
chmod +x "$ROOT/deploy/systemd/dev-update.sh"
systemctl --user daemon-reload
systemctl --user enable --now pravrudhi-app.service pravrudhi-update.timer
systemctl --user list-timers pravrudhi-update.timer --no-pager
