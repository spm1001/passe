# Chrome Debug — a standalone browser for automation

Chrome Debug is a macOS app bundle that wraps Google Chrome with a dedicated user profile and remote debugging enabled. It lives at `~/Applications/Chrome Debug.app` and serves as the runtime for `passe` and any other CDP-based tooling.

## Why a separate app?

Chrome's remote debugging port (`--remote-debugging-port`) is process-wide — you can't enable it for one window and not others. Running automation against your daily browser means every tab is exposed to CDP commands, and your session cookies, history, and extensions are all in scope.

Chrome Debug solves this by being a completely separate Chrome instance:

- **Isolated profile** (`~/.chrome-debug/`) — no crossover with your main browsing data
- **Remote debugging always on** (port 9222) — no need to quit and relaunch Chrome with flags
- **Appears as a separate app** in Dock, Cmd-Tab, and macOS Settings
- **Can be set as default browser** — useful when you want all link clicks to land in the debuggable instance

## What's in the bundle

```
~/Applications/Chrome Debug.app/
└── Contents/
    ├── Info.plist          # App identity + URL scheme registration
    ├── MacOS/
    │   ├── chrome-debug    # Native handler (CFBundleExecutable)
    │   └── launch.sh       # Manual CLI utility (bash, kept for direct use)
    └── Resources/
        └── app.icns        # App icon
```

### chrome-debug (native handler)

The primary executable. A compiled Swift binary (~140 lines, source in `passe/chrome-debug/handler.swift`) that acts as a proper macOS `NSApplication`. This is what macOS runs when you launch Chrome Debug from the Dock, Spotlight, or when it dispatches a URL/file.

**Why native?** Bash can't receive macOS Apple Events (`odoc` for files, `GURL` for URLs). When Chrome Debug is the default browser and you double-click an HTML file or click a link in another app, macOS sends an Apple Event to the running Chrome Debug.app. A bash executable silently drops it — the URL never opens. The native handler receives these events and forwards them to Chrome.

**What it does:**

| Event | Trigger | Handler |
|-------|---------|---------|
| `application:openFiles:` | Double-click .html in Finder, "Open With" | Batch file open via Chrome singleton |
| `kAEGetURL` | Click URL in Slack, Mail, Notes, etc. | URL open via Chrome singleton |
| `applicationShouldHandleReopen:` | Click Chrome Debug in Dock | Brings Chrome window to front |
| `applicationDidFinishLaunching:` | First launch | Starts Chrome with debug flags |
| `on idle` (5s timer) | Ongoing | Quits handler when Chrome exits |

**Re-entry detection** uses Chrome's `SingletonLock` (a symlink encoding the PID). When Chrome is alive, URLs are handed off via `--user-data-dir` only — Chrome's singleton IPC delivers them to the existing instance. When the lock is stale or absent, Chrome is launched with full debug flags.

**First-launch race:** When Chrome Debug launches and immediately receives a file open event, Chrome may not have established its `SingletonLock` yet. The `launchedByUs` flag handles this — if we just started Chrome, URLs are handed off via singleton regardless of lock state (Chrome's own IPC handles the brief race).

**Building and installing:**

```bash
cd ~/Repos/passe/chrome-debug
make            # Compiles universal binary (arm64 + x86_64), ad-hoc signs
make install    # Backs up Info.plist, copies binary, updates CFBundleExecutable, re-registers
```

### launch.sh (manual CLI utility)

Still available at `Contents/MacOS/launch.sh` for direct command-line use. Useful for debugging or launching Chrome Debug outside of macOS app dispatch.

```bash
# Launch Chrome Debug from the terminal
~/Applications/Chrome\ Debug.app/Contents/MacOS/launch.sh

# Open a URL directly
~/Applications/Chrome\ Debug.app/Contents/MacOS/launch.sh https://example.com
```

Includes a re-entry guard (SingletonLock PID check) so running it while Chrome Debug is already running hands off the URL cleanly instead of spawning a second Chrome process.

Key Chrome flags (used by both the native handler and launch.sh):

| Flag | Purpose |
|------|---------|
| `--remote-debugging-port=9222` | Exposes CDP on localhost:9222 for automation tools |
| `--remote-debugging-address=0.0.0.0` | Binds to all interfaces (for Tailscale access from kube) |
| `--remote-allow-origins=*` | Allows CDP connections from any origin |
| `--user-data-dir=~/.chrome-debug` | Completely separate profile, cookies, extensions, history |
| `--no-default-browser-check` | Suppresses the "set as default?" nag on launch |

### Info.plist

The plist registers the app with macOS as a browser by declaring:

- **`CFBundleURLTypes`** with `http` and `https` schemes — this is what makes macOS list it in the "Default web browser" dropdown in System Settings > Desktop & Dock
- **`CFBundleDocumentTypes`** for `public.html`, `public.xhtml`, and `public.url` — so it can open HTML files and URL shortcuts
- **`CFBundleIdentifier`**: `com.modha.chrome-debug` — unique identity, separate from `com.google.Chrome`
- **`LSArchitecturePriority`** set to `arm64` first — prevents macOS from flagging the app for Rosetta (see troubleshooting below)

Without the URL scheme registration, macOS has no way to know the app handles web URLs. It just looks like a random app that happens to launch Chrome.

## Building it from scratch

1. **Create the directory structure:**

```bash
mkdir -p ~/Applications/Chrome\ Debug.app/Contents/{MacOS,Resources}
```

2. **Build and install the native handler:**

```bash
cd ~/Repos/passe/chrome-debug
make && make install
```

This compiles `handler.swift` into a universal binary, ad-hoc signs it, copies it to `Contents/MacOS/chrome-debug`, updates `Info.plist` to use it as `CFBundleExecutable`, and re-registers with Launch Services.

3. **Copy `launch.sh`** to `Contents/MacOS/launch.sh` (optional, for manual CLI use):

```bash
cp ~/Repos/passe/chrome-debug/launch.sh ~/Applications/Chrome\ Debug.app/Contents/MacOS/
chmod +x ~/Applications/Chrome\ Debug.app/Contents/MacOS/launch.sh
```

4. **Add an icon** (optional). Export a `.icns` file as `Contents/Resources/app.icns`. Without it the app gets a generic icon.

5. **Register with Launch Services** (already done by `make install`, but if needed manually):

```bash
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f ~/Applications/Chrome\ Debug.app
```

This forces macOS to re-read the plist. After this, Chrome Debug appears in the default browser dropdown.

## How passe uses it

`passe` connects to Chrome Debug via CDP on `localhost:9222`. The typical flow:

1. Launch Chrome Debug (from Dock, Spotlight, or `open -a "Chrome Debug"`)
2. Run `passe` commands — they discover the browser via `http://localhost:9222/json/version`
3. Automation happens in the isolated profile, leaving your main Chrome untouched

## Troubleshooting

**App doesn't appear in default browser list**
Run `lsregister -f` as shown above. If that doesn't work, log out and back in — Launch Services caches are persistent.

**Port 9222 already in use**
Another Chrome instance (or a previous crash) is holding the port. Find it with `lsof -i :9222` and kill it, or choose a different port in `launch.sh`.

**Extensions / state from main Chrome**
The `--user-data-dir` flag gives Chrome Debug its own profile directory. Nothing is shared with `/Users/you/Library/Application Support/Google/Chrome/`. Install extensions separately in Chrome Debug if needed.

**"Open using Rosetta" keeps getting set**
The native handler is a universal binary (arm64 + x86_64), so this should not occur. If it does (Get Info > "Open using Rosetta"), uncheck it and clear the override:

```bash
xattr -d com.apple.LaunchServices ~/Applications/Chrome\ Debug.app 2>/dev/null
```

Re-run `lsregister -f` afterwards to ensure the registration is clean.

**"Chrome is already running" conflicts**
macOS can run multiple Chrome instances with different `--user-data-dir` values simultaneously. Chrome Debug and regular Chrome coexist without issues. Opening a URL/file while Chrome Debug is already running is handled by the native handler — it receives the Apple Event and hands off to Chrome via singleton IPC.

**Two Chrome dock icons**
Chrome Debug (the native handler) and Google Chrome (the browser process) each create their own dock presence. When regular Chrome is also running, Chrome Debug's Chrome instance merges with regular Chrome's dock icon — you see Chrome Debug + Chrome (two icons, same as before). When regular Chrome is _not_ running, Chrome Debug's Chrome appears as a separate "Google Chrome" icon. This is a macOS limitation — Chrome always creates its own `NSApplication`. Tracked as a known issue.
