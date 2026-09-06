# Pravrudhi Desktop

An Electron desktop application that finds, starts, and supervises your installed Pravrudhi engine. It ships no Python and requires the engine to be installed separately, including its built frontend. See the [engine installation instructions](https://github.com/SharathSPhD/pravrudhi#readme).

From `app/desktop/`, run development with:

```sh
npm install && npm start
```

Choose your project with **Engine → Choose workspace…**, or set `PRAVRUDHI_WORKSPACE` before launch. The selection persists; the initial default is your home folder. The shell does not initialise or modify the workspace itself.

Build the current platform's distributable with:

```sh
npm run dist
```

Linux produces an AppImage. On macOS this produces an **unsigned DMG**; it is not signed or notarized. Build the macOS target on macOS (`npm run dist -- --mac`), and Linux on Linux (`npm run dist -- --linux`). Packaging downloads Electron and builder tools. No engine or Python runtime is included.

The discovery order is `PRAVRUDHI_BIN`, `pravrudhi` on PATH, `~/pravrudhi-release/.pravrudhi/releases/current/.venv/bin/pravrudhi`, `~/.local/bin/pravrudhi`, then the executable remembered by **Locate the engine…**. Invalid/non-executable candidates are skipped. A picked binary does not override an earlier valid candidate; change `PRAVRUDHI_BIN` to explicitly override discovery.

A free loopback port is selected and the shell launches `pravrudhi app --no-browser --port N --root <workspace>`. A real connection screen remains visible until `/api/health` succeeds, with a deadline of 30 seconds. A missing frontend, failed process, or failed health check leads to recovery rather than an empty window. Doctor runs automatically on failure when a binary exists, and can be rerun. Each check displays its engine-provided name and detail with a copyable recovery or diagnostic command. There is no universal command to install Docker on every OS or repair a corrupted ledger; these checks link to installation guidance or advise restoring a verified backup rather than fabricate a repair. Commands are never executed from the renderer.

Native File, View, Engine, and Help menus support additional windows, engine location/restart/stop, workspace access, updates, reload, zoom, developer tools, docs, and version information. A tray menu reflects engine status and can focus the app or restart the engine. Windows share one engine. The first window's focus is restored on a second application launch. Window bounds and maximized state persist in Electron userData, with off-screen recovery. Closing all windows quits on both platforms, terminating the engine process group; SIGINT/SIGTERM also clean up. Graceful termination escalates to SIGKILL if needed.

Update checks invoke `pravrudhi update --json`; applying requires the native prompt and invokes `pravrudhi update --apply --channel release --json`. The engine's ApplyResult reason is shown verbatim. The engine owns all update safeguards. Restart via the Engine menu after an applied update. The check has a bounded command timeout; applying has a longer bounded timeout. The shell itself is updated by installing a new desktop package.

The renderer is sandboxed with context isolation and no Node integration. Its preload exposes only status, locate, restart, stop, doctor, updates, and workspace access through explicitly named invoke calls. IPC validates the sender window, main frame, and origin. New-window requests and navigations send external HTTP(S) links to the system browser; non-web schemes are blocked. Permissions and webviews are denied.

Run the headless logic tests (no GUI is launched):

```sh
node --test test/
```

Tests exercise executable discovery and fallbacks, actual loopback port binding, health retries/deadlines/cancellation, doctor parsing, navigation policy, state persistence, and recovery command quoting. GUI and packaged-artifact smoke tests require a graphical Linux/macOS session.
