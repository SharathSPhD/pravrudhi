#!/usr/bin/env bash
# Ask the installed engine to catch itself up, tolerating whatever version is installed.
#
# A self-updating system must never let its scheduler depend on a flag newer than the engine it is driving.
# `--if-due` was added in 0.2.3; both end-user installs were running 0.2.1, so every scheduled run died on
# "No such option: --if-due" and neither machine could ever update again — the updater disabled itself by
# being improved. So: try the newest invocation, and on an unknown-option error fall back to the oldest one
# that has always existed. Exit 0 either way; a refusal is a safeguard doing its job, not a unit failure.
set -u
ROOT="${1:?install root}"
BIN="$ROOT/.venv/bin/pravrudhi"
[ -x "$BIN" ] || { echo "no engine at $BIN"; exit 0; }

out="$("$BIN" update --apply --if-due --channel release --json --root "$ROOT" 2>&1)"
if printf '%s' "$out" | grep -q "No such option"; then
  out="$("$BIN" update --apply --channel release --json --root "$ROOT" 2>&1)"
fi
echo "$out"
exit 0
