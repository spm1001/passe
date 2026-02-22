#!/bin/bash
# Install the native Chrome Debug handler into the app bundle.
# Run from the chrome-debug/ directory after 'make'.
set -euo pipefail

BINARY="chrome-debug"
APP_DIR="$HOME/Applications/Chrome Debug.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
PLIST="$CONTENTS/Info.plist"

# Sanity checks
if [ ! -f "$BINARY" ]; then
    echo "Error: $BINARY not found. Run 'make' first." >&2
    exit 1
fi

if [ ! -d "$APP_DIR" ]; then
    echo "Error: $APP_DIR not found." >&2
    exit 1
fi

# Back up Info.plist (timestamped, won't overwrite previous backups)
BACKUP="$PLIST.backup-$(date +%Y%m%d-%H%M%S)"
cp "$PLIST" "$BACKUP"
echo "Backed up Info.plist → $(basename "$BACKUP")"

# Copy binary
cp "$BINARY" "$MACOS/$BINARY"
chmod +x "$MACOS/$BINARY"
echo "Installed $BINARY → $MACOS/"

# Update CFBundleExecutable in Info.plist
# Use PlistBuddy (ships with macOS) for safe plist editing
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable $BINARY" "$PLIST"
echo "Updated CFBundleExecutable → $BINARY"

# Re-register with Launch Services so macOS picks up the change
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_DIR"
echo "Re-registered with Launch Services"

echo ""
echo "Done. Quit Chrome Debug and relaunch to use the native handler."
echo "(launch.sh is still in $MACOS/ for manual CLI use)"
