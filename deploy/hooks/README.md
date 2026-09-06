# Pravrudhi guard hook

`pravrudhi_guard.py` is a Claude Code `PreToolUse` hook that keeps an agent
session from accidentally breaking three house rules from this repo's
`CLAUDE.md`:

- committing anything under `pravrudhi_kernel/`, `research/`, `gates/`, or
  `.pravrudhi/` (`git add ...` on those paths is blocked)
- writing a commit message with a `Co-Authored-By:` or `Claude-Session`
  trailer (the repo's `commit-msg` hook rejects these anyway; this stops the
  `git commit` call before it runs)
- editing or writing any file under `pravrudhi_kernel/` (T0 is not the
  agent's to edit)

It reads the hook's stdin JSON (`tool_name`, `tool_input`), and either exits
`2` with a one-line reason on stderr (blocks the call, Claude Code shows the
reason to the model) or exits `0` silently (allows it). Malformed or
unexpected input is allowed through rather than crashing the hook chain.

## Installing

Add it to `~/.claude/settings.json` under the `PreToolUse` hooks for `Bash`,
`Write`, and `Edit`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /absolute/path/to/deploy/hooks/pravrudhi_guard.py"
          }
        ]
      }
    ]
  }
}
```

Use an absolute path to `pravrudhi_guard.py` — hooks are invoked with the
session's working directory as `cwd`, not the repo root, so a relative path
in the hook `command` itself will not resolve reliably. The script has no
third-party dependencies (stdlib only), so any `python3` on `PATH` works.

To install per-project instead of globally, put the same block in the
repo's `.claude/settings.json`.

## Verifying

```bash
echo '{"tool_name": "Bash", "tool_input": {"command": "git add pravrudhi_kernel/foo.py"}}' \
  | python3 deploy/hooks/pravrudhi_guard.py; echo "exit=$?"
```

should print a `pravrudhi_guard: refusing ...` line to stderr and exit `2`.
An ordinary edit or a `git add` on an allowed path exits `0` with no output.

See `tests/test_hooks.py` for the full set of cases the hook is expected to
handle.
