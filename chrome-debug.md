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
    │   └── launch.sh       # Shell wrapper that launches Chrome with flags
    └── Resources/
        └── app.icns        # App icon
```

### launch.sh

```bash
#!/bin/bash
exec "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/.chrome-debug" \
    --no-default-browser-check \
    "$@"
```

Key flags:

| Flag | Purpose |
|------|---------|
| `--remote-debugging-port=9222` | Exposes CDP on localhost:9222 for automation tools |
| `--user-data-dir=~/.chrome-debug` | Completely separate profile, cookies, extensions, history |
| `--no-default-browser-check` | Suppresses the "set as default?" nag on launch |
| `"$@"` | Passes through URL arguments so macOS can open links in it |

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

2. **Write `launch.sh`** at `Contents/MacOS/launch.sh` with the content above, then make it executable:

```bash
chmod +x ~/Applications/Chrome\ Debug.app/Contents/MacOS/launch.sh
```

3. **Create `Info.plist`** at `Contents/Info.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launch.sh</string>
    <key>CFBundleIconFile</key>
    <string>app</string>
    <key>CFBundleIdentifier</key>
    <string>com.modha.chrome-debug</string>
    <key>CFBundleName</key>
    <string>Chrome Debug</string>
    <key>CFBundleDisplayName</key>
    <string>Chrome Debug</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
        <string>x86_64</string>
    </array>
    <key>CFBundleURLTypes</key>
    <array>
        <dict>
            <key>CFBundleURLName</key>
            <string>Web URL</string>
            <key>CFBundleURLSchemes</key>
            <array>
                <string>http</string>
                <string>https</string>
            </array>
        </dict>
    </array>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>HTML Document</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>public.html</string>
                <string>public.xhtml</string>
                <string>public.url</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
```

4. **Add an icon** (optional). Export a `.icns` file as `Contents/Resources/app.icns`. Without it the app gets a generic icon.

5. **Register with Launch Services:**

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
Because the bundle's executable is a shell script (`launch.sh`), macOS can't determine its architecture and sometimes defaults to marking it for Rosetta translation. This is wasteful on Apple Silicon — Chrome itself is a universal binary and runs natively as arm64. The `LSArchitecturePriority` key in the plist tells macOS to prefer arm64, which should prevent the checkbox from appearing. If it gets set anyway (Get Info > "Open using Rosetta"), uncheck it. You can also clear it from the command line:

```bash
# Check current state
xattr -p com.apple.LaunchServices ~/Applications/Chrome\ Debug.app 2>/dev/null

# Remove Rosetta override if set
xattr -d com.apple.LaunchServices ~/Applications/Chrome\ Debug.app 2>/dev/null
```

Re-run `lsregister -f` afterwards to ensure the registration is clean.

**"Chrome is already running" conflicts**
macOS can run multiple Chrome instances with different `--user-data-dir` values simultaneously. Chrome Debug and regular Chrome coexist without issues.
