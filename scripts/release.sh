#!/bin/bash
set -e

# ── Config ────────────────────────────────────────────────────────────
APP_NAME="AppStoreScreens"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUNDLE_DIR="$PROJECT_DIR/src-tauri/target/release/bundle/macos"
APP_PATH="$BUNDLE_DIR/$APP_NAME.app"

# ── Bump version ─────────────────────────────────────────────────────
OLD_VERSION=$(python3 -c "import json; print(json.load(open('$PROJECT_DIR/src-tauri/tauri.conf.json'))['version'])")
BUMP_TYPE="${1:-patch}"

IFS='.' read -r MAJOR MINOR PATCH <<< "$OLD_VERSION"
case "$BUMP_TYPE" in
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    patch) PATCH=$((PATCH + 1)) ;;
    *) echo "Usage: $0 [patch|minor|major]"; exit 1 ;;
esac
VERSION="$MAJOR.$MINOR.$PATCH"

# Update all version files
python3 << PYEOF
import json, pathlib
for f, key in [('src-tauri/tauri.conf.json', 'version'), ('package.json', 'version')]:
    p = pathlib.Path('$PROJECT_DIR') / f
    d = json.loads(p.read_text())
    d[key] = '$VERSION'
    p.write_text(json.dumps(d, indent=2) + '\n')
PYEOF
sed -i '' "s/^version = \"$OLD_VERSION\"/version = \"$VERSION\"/" "$PROJECT_DIR/src-tauri/Cargo.toml"

TAG="v$VERSION"
ZIP_NAME="AppStoreScreens-$VERSION-aarch64-apple-darwin.zip"
ZIP_PATH="$BUNDLE_DIR/$ZIP_NAME"

echo "═══════════════════════════════════════════"
echo "  $APP_NAME  $OLD_VERSION → $VERSION"
echo "═══════════════════════════════════════════"
echo ""

# ── Check signing identity ────────────────────────────────────────────
SIGNING_IDENTITY=""
if security find-identity -v -p codesigning 2>/dev/null | grep -q "Developer ID Application"; then
    SIGNING_IDENTITY=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
    echo "▸ Signing identity: $SIGNING_IDENTITY"
else
    echo "▸ No Developer ID — app will be unsigned"
fi
echo ""

# ── Build ─────────────────────────────────────────────────────────────
echo "▸ Building..."
cd "$PROJECT_DIR"

export TAURI_SIGNING_PRIVATE_KEY=$(cat "$PROJECT_DIR/src-tauri/tauri.key" 2>/dev/null || echo "")
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-appscreen123}"

npx @tauri-apps/cli build 2>&1 | tail -5

if [ ! -d "$APP_PATH" ]; then
    echo "✗ Build failed — $APP_PATH not found"
    exit 1
fi
echo "✓ Built"
echo ""

# ── Sign ──────────────────────────────────────────────────────────────
if [ -n "$SIGNING_IDENTITY" ]; then
    echo "▸ Signing..."
    codesign --force --deep --options runtime \
        --entitlements "$PROJECT_DIR/src-tauri/Entitlements.plist" \
        --sign "$SIGNING_IDENTITY" "$APP_PATH"
    echo "✓ Signed"
    echo ""
fi

# ── Zip ───────────────────────────────────────────────────────────────
echo "▸ Zipping..."
rm -f "$ZIP_PATH"
cd "$BUNDLE_DIR"
zip -rq "$ZIP_NAME" "$APP_NAME.app" -x "*.DS_Store"
SIZE=$(du -h "$ZIP_PATH" | awk '{print $1}')
echo "✓ $ZIP_NAME ($SIZE)"
echo ""

# ── Notarize ──────────────────────────────────────────────────────────
if [ -n "$SIGNING_IDENTITY" ]; then
    echo "▸ Notarizing..."
    if command -v asc &>/dev/null && asc auth check &>/dev/null 2>&1; then
        asc notarization submit --file "$ZIP_PATH" --wait 2>&1 | tail -3
        xcrun stapler staple "$APP_PATH" 2>/dev/null && echo "✓ Stapled" || true
        # Re-zip with stapled ticket
        rm -f "$ZIP_PATH"
        cd "$BUNDLE_DIR"
        zip -rq "$ZIP_NAME" "$APP_NAME.app" -x "*.DS_Store"
    else
        echo "  asc not available — skipping"
    fi
    echo ""
fi

# ── Commit & tag ──────────────────────────────────────────────────────
echo "▸ Committing..."
cd "$PROJECT_DIR"
git add src-tauri/tauri.conf.json src-tauri/Cargo.toml src-tauri/Cargo.lock package.json 2>/dev/null || true
git commit -m "chore: bump version to $VERSION" 2>/dev/null || true
git push origin main 2>/dev/null || true
echo "✓ Pushed"
echo ""

# ── GitHub Release ────────────────────────────────────────────────────
echo "▸ Creating release $TAG..."

# Build latest.json for auto-updater
SIG_FILE="${ZIP_PATH}.sig"
SIG=""
[ -f "$SIG_FILE" ] && SIG=$(cat "$SIG_FILE")

cat > "$BUNDLE_DIR/latest.json" << ENDJSON
{
  "version": "$VERSION",
  "notes": "$APP_NAME v$VERSION",
  "pub_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "platforms": {
    "darwin-aarch64": {
      "signature": "$SIG",
      "url": "https://github.com/barrault01/appscreen/releases/download/$TAG/$ZIP_NAME"
    }
  }
}
ENDJSON

# Delete old release if exists
gh release delete "$TAG" --yes 2>/dev/null || true
git tag -d "$TAG" 2>/dev/null || true
git push origin ":refs/tags/$TAG" 2>/dev/null || true

# Create tag and release
git tag "$TAG"
git push origin "$TAG"

gh release create "$TAG" \
    --title "$APP_NAME v$VERSION" \
    --notes "## $APP_NAME v$VERSION

### Install
Download the zip, extract, drag to Applications." \
    "$ZIP_PATH#$APP_NAME (macOS Apple Silicon)" \
    "$BUNDLE_DIR/latest.json"

RELEASE_URL=$(gh release view "$TAG" --json url -q '.url')
echo ""
echo "═══════════════════════════════════════════"
echo "  ✓ $RELEASE_URL"
echo "═══════════════════════════════════════════"
