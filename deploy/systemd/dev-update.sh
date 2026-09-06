#!/usr/bin/env bash
# Apply a developer-channel update if one is safe to apply, then restart the running app only when it changed.
# Exit 0 whether or not anything was applied: a refusal is the safeguard working, not a failure of this unit.
set -u
ROOT="${1:?checkout root}"
cd "$ROOT" || exit 1
out="$("$ROOT/.venv/bin/python" -m pravrudhi update --apply --channel dev --json 2>&1)"
echo "$out"
if printf '%s' "$out" | grep -q '"applied": true'; then
  systemctl --user try-restart pravrudhi-app.service
fi
exit 0
