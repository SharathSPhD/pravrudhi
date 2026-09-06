#!/usr/bin/env bash
# Ask the installed engine to catch itself up, using whatever version is actually installed.
#
# TWO TRAPS THIS AVOIDS, both found by running it on two machines rather than by reading it.
#
# 1. The updater that runs must be the updater that was installed. The bootstrap venv exists only to install the
#    first release and is never upgraded afterwards, so calling it forever pins the update logic to the version
#    the machine started life with: both end-user installs re-downloaded and re-installed the same release every
#    thirty minutes, because the bootstrap was 0.2.1 and the idempotency check arrived in 0.2.3. Prefer the
#    release that `current` points at, and fall back to the bootstrap only before the first release is in place.
#
# 2. A scheduler must never depend on a flag newer than the engine it drives. `--if-due` arrived in 0.2.3; while
#    the installs were on 0.2.1 every scheduled run died on "No such option" and neither machine could update
#    again — the updater disabled itself by being improved. Try the newest invocation, fall back to the oldest.
#
# Exit 0 either way: a refusal is a safeguard doing its job, not a unit failure.
set -u
ROOT="${1:?install root}"

CURRENT="$ROOT/.pravrudhi/releases/current/.venv/bin/pravrudhi"
BOOTSTRAP="$ROOT/.venv/bin/pravrudhi"
if [ -x "$CURRENT" ]; then BIN="$CURRENT"; elif [ -x "$BOOTSTRAP" ]; then BIN="$BOOTSTRAP"; else
  echo "no engine under $ROOT"; exit 0
fi

out="$("$BIN" update --apply --if-due --channel release --json --root "$ROOT" 2>&1)"
if printf '%s' "$out" | grep -q "No such option"; then
  out="$("$BIN" update --apply --channel release --json --root "$ROOT" 2>&1)"
fi
echo "$out"
exit 0
