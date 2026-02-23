#!/bin/bash
# Install the Chrome Passe native handler into the app bundle.
# Run from the chrome-passe/ directory after 'make'.
set -euo pipefail

BINARY="chrome-passe"
APP_DIR="$HOME/Applications/Chrome Passe.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
PLIST="$CONTENTS/Info.plist"
ICNS_SRC="/tmp/chrome_passe.icns"

# Create the app bundle structure if it doesn't exist
mkdir -p "$MACOS" "$RESOURCES"

# Create or update Info.plist
cat > "$PLIST" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Chrome Passe</string>
    <key>CFBundleIdentifier</key>
    <string>com.modha.chrome-passe</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>chrome-passe</string>
    <key>CFBundleDisplayName</key>
    <string>Chrome Passe</string>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
        <string>x86_64</string>
    </array>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>public.html</string>
                <string>public.xhtml</string>
                <string>public.url</string>
            </array>
            <key>CFBundleTypeName</key>
            <string>HTML Document</string>
        </dict>
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
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>app</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
</dict>
</plist>
PLIST
echo "Wrote Info.plist"

# Copy binary
cp "$BINARY" "$MACOS/$BINARY"
chmod +x "$MACOS/$BINARY"
echo "Installed $BINARY → $MACOS/"

# Copy icon if available
if [ -f "$ICNS_SRC" ]; then
    cp "$ICNS_SRC" "$RESOURCES/app.icns"
    echo "Installed icon → $RESOURCES/app.icns"
elif [ -f "app.icns" ]; then
    cp "app.icns" "$RESOURCES/app.icns"
    echo "Installed icon → $RESOURCES/app.icns"
else
    echo "Warning: no icon found (checked $ICNS_SRC and ./app.icns)"
fi

# Re-register with Launch Services so macOS picks up the change
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_DIR"
echo "Re-registered with Launch Services"

echo ""
echo "Done. Chrome Passe.app is ready at $APP_DIR"
echo "You can set it as your default browser in System Settings > Desktop & Dock."
