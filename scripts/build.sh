#!/bin/bash
set -euo pipefail

# Build and package the appscreen Tauri app for macOS
# Usage:
#   ./scripts/build.sh              # Build .dmg (unsigned)
#   ./scripts/build.sh --universal  # Build universal binary (Intel + Apple Silicon)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

UNIVERSAL=false
for arg in "$@"; do
    case "$arg" in
        --universal) UNIVERSAL=true ;;
    esac
done

echo "==> Building appscreen"

# Read version from tauri.conf.json
VERSION=$(grep '"version"' src-tauri/tauri.conf.json | head -1 | sed 's/.*: *"\(.*\)".*/\1/')
echo "    Version: $VERSION"

# Build
if [ "$UNIVERSAL" = true ]; then
    echo "    Target: universal (aarch64 + x86_64)"
    npm run tauri build -- --target universal-apple-darwin
else
    echo "    Target: native"
    npm run tauri build
fi

# Find the built artifacts
BUNDLE_DIR="$PROJECT_DIR/src-tauri/target"
if [ "$UNIVERSAL" = true ]; then
    BUNDLE_DIR="$BUNDLE_DIR/universal-apple-darwin"
fi
BUNDLE_DIR="$BUNDLE_DIR/release/bundle"

DMG=$(find "$BUNDLE_DIR/dmg" -name "*.dmg" 2>/dev/null | head -1)
APP=$(find "$BUNDLE_DIR/macos" -name "*.app" -maxdepth 1 2>/dev/null | head -1)

echo ""
echo "==> Build complete"
if [ -n "$APP" ]; then
    echo "    App: $APP"
    APP_SIZE=$(du -sh "$APP" | cut -f1)
    echo "    Size: $APP_SIZE"
fi
if [ -n "$DMG" ]; then
    echo "    DMG: $DMG"
    DMG_SIZE=$(du -sh "$DMG" | cut -f1)
    echo "    Size: $DMG_SIZE"
fi
