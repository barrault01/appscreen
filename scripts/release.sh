#!/bin/bash
set -e

# Release script for yuzu.shot
# Usage: ./scripts/release.sh [patch|minor|major]
# Example: ./scripts/release.sh patch  → 1.1.0 → 1.1.1
#          ./scripts/release.sh minor  → 1.1.0 → 1.2.0
#          ./scripts/release.sh major  → 1.1.0 → 2.0.0

BUMP_TYPE="${1:-patch}"

# Get current version from package.json
CURRENT_VERSION=$(node -p "require('./package.json').version")
echo "Current version: $CURRENT_VERSION"

# Calculate new version
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"
case "$BUMP_TYPE" in
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    patch) PATCH=$((PATCH + 1)) ;;
    *) echo "Usage: $0 [patch|minor|major]"; exit 1 ;;
esac
NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
echo "New version: $NEW_VERSION"

# Confirm
read -p "Release v${NEW_VERSION}? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Update version in all files
echo "Updating version in package.json..."
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
pkg.version = '${NEW_VERSION}';
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
"

echo "Updating version in src-tauri/tauri.conf.json..."
node -e "
const fs = require('fs');
const conf = JSON.parse(fs.readFileSync('src-tauri/tauri.conf.json', 'utf8'));
conf.version = '${NEW_VERSION}';
fs.writeFileSync('src-tauri/tauri.conf.json', JSON.stringify(conf, null, 2) + '\n');
"

echo "Updating version in src-tauri/Cargo.toml..."
sed -i '' "s/^version = \".*\"/version = \"${NEW_VERSION}\"/" src-tauri/Cargo.toml

# Commit and tag
echo "Committing version bump..."
git add package.json src-tauri/tauri.conf.json src-tauri/Cargo.toml
git commit -m "chore: bump version to ${NEW_VERSION}"

echo "Creating tag v${NEW_VERSION}..."
git tag "v${NEW_VERSION}"

echo "Pushing to origin..."
git push origin main
git push origin "v${NEW_VERSION}"

echo ""
echo "✅ Release v${NEW_VERSION} triggered!"
echo ""
echo "GitHub Actions will now:"
echo "  1. Build for macOS (arm64 + x86), Linux, and Windows"
echo "  2. Sign the update artifacts"
echo "  3. Create a GitHub Release with all binaries"
echo "  4. Upload latest.json for auto-updates"
echo ""
echo "Track progress: https://github.com/barrault01/appscreen/actions"
