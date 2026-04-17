#!/bin/bash
set -e

# ── Config ────────────────────────────────────────────────────────────
APP_NAME="yuzu.shot"
BUNDLE_ID="com.yuzuhub.yuzushot"
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

# Update tauri.conf.json
python3 -c "
import json, pathlib
p = pathlib.Path('$PROJECT_DIR/src-tauri/tauri.conf.json')
d = json.loads(p.read_text())
d['version'] = '$VERSION'
p.write_text(json.dumps(d, indent=2) + '\n')
"

# Update Cargo.toml
sed -i '' "s/^version = \"$OLD_VERSION\"/version = \"$VERSION\"/" "$PROJECT_DIR/src-tauri/Cargo.toml"

# Update package.json
python3 -c "
import json, pathlib
p = pathlib.Path('$PROJECT_DIR/package.json')
d = json.loads(p.read_text())
d['version'] = '$VERSION'
p.write_text(json.dumps(d, indent=2) + '\n')
"

echo "▸ Bumped version: $OLD_VERSION → $VERSION"

TAG="v$VERSION"
ZIP_NAME="yuzu.shot-$VERSION-aarch64-apple-darwin.zip"
ZIP_PATH="$BUNDLE_DIR/$ZIP_NAME"

echo "═══════════════════════════════════════════"
echo "  $APP_NAME v$VERSION — Release Script"
echo "═══════════════════════════════════════════"
echo ""

# ── Check tools ───────────────────────────────────────────────────────
echo "▸ Checking tools..."
source "$HOME/.cargo/env" 2>/dev/null || true

for cmd in node npm cargo gh; do
  if ! command -v $cmd &>/dev/null; then
    echo "  ✗ $cmd not found"
    exit 1
  fi
  echo "  ✓ $cmd"
done

# Check for Apple Developer ID
SIGNING_IDENTITY=""
if security find-identity -v -p codesigning 2>/dev/null | grep -q "Developer ID Application"; then
  SIGNING_IDENTITY=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
  echo "  ✓ Signing: $SIGNING_IDENTITY"
else
  echo "  ⚠ No Developer ID — app will be unsigned"
fi

echo ""

# ── Build ─────────────────────────────────────────────────────────────
echo "▸ Building Tauri app..."
cd "$PROJECT_DIR"

# Set signing key for updater
export TAURI_SIGNING_PRIVATE_KEY=$(cat "$PROJECT_DIR/src-tauri/tauri.key" 2>/dev/null || echo "")
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-appscreen123}"

PATH="$HOME/.cargo/bin:$PATH" npx @tauri-apps/cli build 2>&1 | grep -E "Compiling yuzu|Finished|Bundling|error\[" || true

if [ ! -d "$APP_PATH" ]; then
  echo "  ✗ Build failed — $APP_PATH not found"
  exit 1
fi
echo "  ✓ Built: $APP_PATH"
echo ""

# ── Sign ──────────────────────────────────────────────────────────────
if [ -n "$SIGNING_IDENTITY" ]; then
  echo "▸ Signing app..."
  codesign --force --deep --options runtime \
    --entitlements "$PROJECT_DIR/src-tauri/Entitlements.plist" \
    --sign "$SIGNING_IDENTITY" "$APP_PATH"
  codesign --verify --verbose "$APP_PATH" 2>&1 | tail -1
  echo "  ✓ Signed"
  echo ""
else
  echo "▸ Skipping signing (no Developer ID)"
  echo ""
fi

# ── Zip ───────────────────────────────────────────────────────────────
echo "▸ Creating zip..."
rm -f "$ZIP_PATH"
cd "$BUNDLE_DIR"
zip -r "$ZIP_NAME" "$APP_NAME.app" -x "*.DS_Store"
SIZE=$(du -h "$ZIP_PATH" | awk '{print $1}')
echo "  ✓ $ZIP_NAME ($SIZE)"
echo ""

# ── Notarize ──────────────────────────────────────────────────────────
if [ -n "$SIGNING_IDENTITY" ] && command -v xcrun &>/dev/null; then
  echo "▸ Notarizing..."

  # Try asc first, then xcrun notarytool
  if command -v asc &>/dev/null && asc auth check &>/dev/null 2>&1; then
    NOTARIZE_OUTPUT=$(asc notarization submit --file "$ZIP_PATH" --wait --output json 2>&1) || true
    echo "$NOTARIZE_OUTPUT"
  else
    echo "  ⚠ asc not available — skipping notarization"
    echo "  To notarize manually: xcrun notarytool submit $ZIP_PATH --wait"
  fi

  # Staple if notarization succeeded
  if xcrun stapler staple "$APP_PATH" 2>/dev/null; then
    echo "  ✓ Stapled"
    # Re-zip with stapled app
    echo "▸ Re-zipping with stapled ticket..."
    rm -f "$ZIP_PATH"
    cd "$BUNDLE_DIR"
    zip -r "$ZIP_NAME" "$APP_NAME.app" -x "*.DS_Store"
    echo "  ✓ Re-zipped"
  fi
  echo ""
else
  echo "▸ Skipping notarization"
  echo ""
fi

# ── Commit & Push ────────────────────────────────────────────────────
echo "▸ Committing version bump..."
cd "$PROJECT_DIR"
git add src-tauri/tauri.conf.json src-tauri/Cargo.toml src-tauri/Cargo.lock package.json 2>/dev/null || true
git commit -m "chore: bump version to $VERSION" || echo "  (nothing to commit)"
git push origin main
echo "  ✓ Pushed"
echo ""

# ── GitHub Release ────────────────────────────────────────────────────
echo "▸ Creating GitHub release $TAG..."

# Generate latest.json for auto-updater
LATEST_JSON="$BUNDLE_DIR/latest.json"
SIG_FILE="$BUNDLE_DIR/$ZIP_NAME.sig"
SIGNATURE=""
if [ -f "$SIG_FILE" ]; then
  SIGNATURE=$(cat "$SIG_FILE")
fi

cat > "$LATEST_JSON" << ENDJSON
{
  "version": "$VERSION",
  "notes": "yuzu.shot v$VERSION",
  "pub_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "platforms": {
    "darwin-aarch64": {
      "signature": "$SIGNATURE",
      "url": "https://github.com/barrault01/appscreen/releases/download/$TAG/$ZIP_NAME"
    }
  }
}
ENDJSON

if gh release view "$TAG" &>/dev/null; then
  echo "  Release $TAG exists — updating assets..."
  gh release delete-asset "$TAG" "$ZIP_NAME" --yes 2>/dev/null || true
  gh release delete-asset "$TAG" "latest.json" --yes 2>/dev/null || true
  gh release upload "$TAG" "$ZIP_PATH#$APP_NAME (macOS Apple Silicon)" "$LATEST_JSON"
  echo "  ✓ Updated"
else
  gh release create "$TAG" \
    --title "$APP_NAME v$VERSION" \
    --notes "## $APP_NAME v$VERSION

### What's New
- ASO Badges (Editor's Choice, App of the Year, stats badges with laurel wreaths)
- Template Presets (8 one-click screenshot styles)
- Background Patterns (dots, grid, diagonal lines, waves, mesh)
- Screenshot Color Extraction (auto-suggest gradients from your screenshot)
- Gradient Text (headline gradient fills)
- Auto-update support

### Install
1. Download the zip below
2. Extract and drag \`$APP_NAME.app\` to Applications

### Requirements
- macOS 10.15+" \
    "$ZIP_PATH#$APP_NAME (macOS Apple Silicon)" \
    "$LATEST_JSON"
  echo "  ✓ Created"
fi

# Also push the tag
git tag "$TAG" 2>/dev/null || true
git push origin "$TAG" 2>/dev/null || true

RELEASE_URL=$(gh release view "$TAG" --json url -q '.url')
echo ""
echo "═══════════════════════════════════════════"
echo "  ✓ Done! $RELEASE_URL"
echo "═══════════════════════════════════════════"
