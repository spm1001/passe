# Chrome Passe — a standalone browser for automation

Chrome Passe is a macOS app bundle that wraps Google Chrome with a dedicated user profile and remote debugging enabled. It lives at `~/Applications/Chrome Passe.app` and serves as the runtime for `passe` and any other CDP-based tooling.

## Why a separate app?

Chrome's remote debugging port (`--remote-debugging-port`) is process-wide — you can't enable it for one window and not others. Running automation against your daily browser means every tab is exposed to CDP commands, and your session cookies, history, and extensions are all in scope.

Chrome Passe solves this by being a completely separate Chrome instance:

- **Isolated profile** (`~/.chrome-passe/`) — no crossover with your main browsing data
- **Remote debugging always on** (port 9222) — no need to quit and relaunch Chrome with flags
- **Appears as a separate app** in Dock, Cmd-Tab, and macOS Settings
- **Can be set as default browser** — useful when you want all link clicks to land in the debuggable instance

## What's in the bundle

```
~/Applications/Chrome Passe.app/
└── Contents/
    ├── Info.plist          # App identity + URL scheme registration
    ├── MacOS/
    │   └── chrome-passe    # Native handler (CFBundleExecutable)
    └── Resources/
        └── app.icns        # App icon (Chrome ring with P monogram)
```

### chrome-passe (native handler)

The primary executable. A compiled Swift binary (~140 lines, source in `passe/chrome-passe/handler.swift`) that acts as a proper macOS `NSApplication`. This is what macOS runs when you launch Chrome Passe from the Dock, Spotlight, or when it dispatches a URL/file.

**Why native?** Bash can't receive macOS Apple Events (`odoc` for files, `GURL` for URLs). When Chrome Passe is the default browser and you double-click an HTML file or click a link in another app, macOS sends an Apple Event to the running Chrome Passe.app. A bash executable silently drops it — the URL never opens. The native handler receives these events and forwards them to Chrome.

**Launch method: NSWorkspace.** Chrome is launched via `NSWorkspace.shared.openApplication()` rather than `Process()` or bash. This is critical — when a wrapper app spawns Chrome via `Process()`, Chrome inherits the wrapper's TCC coalition. macOS then checks the *wrapper's* Info.plist for privacy usage descriptions (microphone, camera, etc.), and crashes Chrome with SIGABRT when they're missing. NSWorkspace launches Chrome through LaunchServices, giving it its own coalition and its own TCC grants. Trade-off: Chrome gets its own dock icon (two icons total). Worth it — a browser that crashes on Google Meet is useless.

**What it does:**

| Event | Trigger | Handler |
|-------|---------|---------|
| `application:openFiles:` | Double-click .html in Finder, "Open With" | Opens file URLs in Chrome via NSWorkspace |
| `kAEGetURL` | Click URL in Slack, Mail, Notes, etc. | Opens URL in Chrome via NSWorkspace |
| `applicationShouldHandleReopen:` | Click Chrome Passe in Dock | Brings Chrome window to front |
| `applicationDidFinishLaunching:` | First launch | Starts Chrome with debug flags via NSWorkspace |
| `on idle` (5s timer) | Ongoing | Quits handler when Chrome exits |

**Re-entry detection** uses Chrome's `SingletonLock` (a symlink encoding the PID). When Chrome is alive, URLs are opened via `NSWorkspace.shared.open(urls, withApplicationAt:)` — Chrome's singleton IPC delivers them to the existing instance. When the lock is stale or absent, Chrome is launched with full debug flags.

**First-launch race:** When Chrome Passe launches and immediately receives a file open event, Chrome may not have established its `SingletonLock` yet. The `launchedByUs` flag handles this — if we just started Chrome, URLs are handed off regardless of lock state.

**Building and installing:**

```bash
cd ~/Repos/passe/chrome-passe
make            # Compiles universal binary (arm64 + x86_64), ad-hoc signs
make install    # Creates app bundle, writes Info.plist, copies binary + icon, re-registers
```

Key Chrome flags passed via `NSWorkspace.OpenConfiguration.arguments`:

| Flag | Purpose |
|------|---------|
| `--remote-debugging-port=9222` | Exposes CDP on localhost:9222 for automation tools |
| `--remote-allow-origins=*` | Allows CDP connections from any origin |
| `--user-data-dir=~/.chrome-passe` | Completely separate profile, cookies, extensions, history |
| `--no-default-browser-check` | Suppresses the "set as default?" nag on launch |

### Info.plist

The plist registers the app with macOS as a browser by declaring:

- **`CFBundleURLTypes`** with `http` and `https` schemes — this is what makes macOS list it in the "Default web browser" dropdown in System Settings > Desktop & Dock
- **`CFBundleDocumentTypes`** for `public.html`, `public.xhtml`, and `public.url` — so it can open HTML files and URL shortcuts
- **`CFBundleIdentifier`**: `com.modha.chrome-passe` — unique identity, separate from `com.google.Chrome`
- **`LSArchitecturePriority`** set to `arm64` first — prevents macOS from flagging the app for Rosetta

The Info.plist is written fresh by `install.sh` — no need to maintain it separately.

## Building it from scratch

1. **Build and install:**

```bash
cd ~/Repos/passe/chrome-passe
make && make install
```

This compiles `handler.swift` into a universal binary, ad-hoc signs it, creates the full app bundle at `~/Applications/Chrome Passe.app` (with Info.plist, icon, and binary), and re-registers with Launch Services.

2. **Verify** — Chrome Passe should appear in System Settings > Desktop & Dock > Default web browser.

## How passe uses it

`passe` connects to Chrome Passe via CDP on `localhost:9222`. The typical flow:

1. Launch Chrome Passe (from Dock, Spotlight, or `open -a "Chrome Passe"`)
2. Run `passe` commands — they discover the browser via `http://localhost:9222/json/version`
3. Automation happens in the isolated profile, leaving your main Chrome untouched

## Troubleshooting

**App doesn't appear in default browser list**
Run `lsregister -f` on the app bundle. If that doesn't work, log out and back in — Launch Services caches are persistent.

**Port 9222 already in use**
Another Chrome instance (or a previous crash) is holding the port. Find it with `lsof -i :9222` and kill it.

**Extensions / state from main Chrome**
The `--user-data-dir` flag gives Chrome Passe its own profile directory. Nothing is shared with `/Users/you/Library/Application Support/Google/Chrome/`. Install extensions separately if needed.

**"Open using Rosetta" keeps getting set**
The native handler is a universal binary (arm64 + x86_64), so this should not occur. If it does, uncheck it in Get Info and clear the override:

```bash
xattr -d com.apple.LaunchServices ~/Applications/Chrome\ Passe.app 2>/dev/null
```

Re-run `lsregister -f` afterwards.

**Two dock icons**
Expected. Chrome Passe (the native handler) and Google Chrome (the browser process) each have their own dock presence. This is the trade-off for Chrome having its own TCC coalition — microphone, camera, and all other privacy-gated APIs work correctly. The alternative (Chrome inheriting the wrapper's coalition) causes Chrome to crash with SIGABRT when any TCC-gated API is accessed.

**Migrating from Chrome Debug**
If you previously used Chrome Debug (`~/.chrome-debug`), your bookmarks and history are in the old profile. Either copy `~/.chrome-debug` to `~/.chrome-passe`, or start fresh (the debug profile is typically bare anyway).
