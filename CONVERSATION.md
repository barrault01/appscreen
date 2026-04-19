# AppStoreScreens — Build Session Log

## Starting Point

Started from **Siftly** (a Twitter/X bookmark manager). Searched all 477 bookmarks for App Store screenshot-related content and found key references:

- **$70k/mo ASO Screenshot Workflow** — Claude Skill that reads code, extracts benefits, generates headlines, directs screenshot composition
- **Koubou** (bitomule/Koubou) — Python CLI for YAML-driven screenshot generation with device frames, annotations, zoom callouts, HTML templates, localization via xcstrings
- **RespectASO** — free local ASO keyword research tool
- **Sketch MCP** for screenshot localization
- **Marketing playbook** — "the code didn't change, the marketing did"
- **ParthJadhav/app-store-screenshots** — Claude skill using html-to-image with mockup overlays
- **JorgeFrias/Automated-AppStore-Screenshots** — SwiftUI-based screenshot automation
- **adamlyttleapps/claude-skill-aso-appstore-screenshots** — Pillow scaffold + Gemini enhancement pipeline

## Phase 1: Standalone Screenshot Builder (Next.js)

Built a standalone Next.js app at `~/Documents/repos/perso/ScreenshotBuilder/`:

- **Device frames** — iPhone 16 Pro Max, 15 Pro Max, iPad Pro 13", 11" at exact App Store pixel dimensions
- **Layout templates** — Text Top, Text Bottom, Split Left, Full Screen, Hero Center, Multi-2, Multi-3, Multi-Fan
- **Gradient presets** — 18 gradient backgrounds + custom color pickers
- **AI headline generation** — Anthropic SDK generating ASO-optimized headlines
- **AI full deck** — describe app, AI generates 4-6 slides with varied layouts, headlines, decorations, screenshot instructions
- **AI screenshot analysis** — vision API analyzes uploaded screenshot, suggests headlines + gradient
- **Localization** — 15 languages, AI transcreation (not literal translation)
- **Batch upload** — drop multiple screenshots, auto-create slides
- **Multi-device export** — export all slides at every required device size
- **Background patterns** — dot grid, diagonal lines, mesh, waves, noise
- **Screenshot color extraction** — auto-extract dominant colors, suggest matching gradients
- **Gradient text** — headline text with gradient fills
- **Decorations** — sparkles, confetti, circles, dots, stars, floating lines
- **Badges** — App Store-style badges with laurel wreaths
- **Callouts** — spotlight circles on device screenshots
- **Device colors** — Black, White, Natural, Desert Titanium
- **Real device frame PNGs** — from Exports folder, overlaid on screenshots
- **Template presets** — 8 pre-built full-deck configurations

## Phase 2: Discovered appscreen (YuzuHub)

Found `~/Documents/repos/perso/appscreen/` — an existing open-source tool that already had most features:

- 2D + 3D device mockups (Three.js + GLTF models)
- Gradient backgrounds with draggable color stops
- Text overlays with 1500+ Google Fonts
- Multi-language support with per-language screenshots
- AI headlines via Claude/OpenAI/Gemini vision
- Popouts, elements, emojis, icons
- Batch export as ZIP
- IndexedDB persistence
- Tauri desktop app

## Phase 3: Added Features to appscreen

### PR #1: ASO Badges + Template Presets + Background Patterns + Color Extraction + Gradient Text

**ASO Badges** — 11 badge presets across 3 categories:
- **Apple Awards** (5): Editor's Choice, App of the Year, Featured by App Store, App of the Day, Apple Spotlight — using real SVG laurel wreaths from `img/laurel-detailed-left.svg`
- **Stats** (5): 100K+ Reviews, 1M+ Downloads, 5M+ Downloads, 5 Star Rated, #1 Most Downloaded — with star ratings, large numbers
- **Social Proof** (1): Review quote card with stars and attribution
- Editable text fields per line, per-line text scale sliders (50%-200%), color picker
- Badge type selector with optgroups

**Template Presets** — 8 one-click templates in Background tab:
- Clean Minimal, Editor's Choice, Bold Marketing, App of the Day, Pastel Soft, Dark Premium, Gradient Hero, Perspective
- Each configures gradient + device position/scale + text size/color/weight + optional badge

**Background Patterns** — 5 pattern overlays:
- Dots, Grid, Diagonal Lines, Waves, Mesh
- Scale, Opacity, Color controls
- Works in both preview and export

**Screenshot Color Extraction** — auto-extracts 5 dominant colors:
- Displays as clickable swatches above gradient presets
- Click to generate matching gradient
- Suggested gradient swatch from top 2 colors

**Gradient Text** — headline gradient fills:
- Toggle on/off, direction angle, start/end color pickers
- Works in both preview and export

### PR #2: Auto-Update + Release Pipeline

- **tauri-plugin-updater** for automatic app updates
- Checks for updates on launch, downloads and installs
- **Signing keypair** generated, private key in GitHub Secrets
- **CI workflow** builds for macOS arm64/x86, Linux, Windows, signs artifacts
- **release.sh** script for version bumping + build + sign + notarize + GitHub Release
- `latest.json` uploaded with each release for the updater endpoint

## Phase 4: Rename + Polish

- Renamed from `yuzu.shot` to `AppStoreScreens` across all files
- Updated bundle ID to `com.barrault.appstorescreen`
- Updated README authorship — credit original creator (Stefan/YuzuHub), add current maintainer (Antoine Barrault)
- Version reset to 1.0.0

## Phase 5: 3D Mockup Fix

**Problem:** 3D device mockups showed empty in Tauri desktop app but worked in browser.

**Root cause:** Three.js was loaded from CDN (`cdnjs.cloudflare.com`, `cdn.jsdelivr.net`). Tauri WebView in production mode blocks external script loads.

**Fix:** Downloaded Three.js, GLTFLoader.js, OrbitControls.js into `vendor/` and referenced them locally.

## Phase 6: Badge Iterations

Multiple rounds of refinement based on reference screenshots:

1. **v1** — Simple colored pill badges with basic icons → too flat/generic
2. **v2** — Frosted glass badges with backdrop blur → wrong style entirely
3. **v3** — Laurel wreath badges (programmatic) → leaves too big/blobby, overlapping text
4. **v4** — Bezier curve leaves → still not right
5. **v5** — Real SVG laurel wreaths from `img/laurel-detailed-left.svg` → much better
6. **v6** — Fixed text centering, added vertical spacing, per-line text scale sliders
7. **Final** — Proper vertical centering via content height pre-calculation, editable text fields

Reference images studied: Apple Editor's Choice, App of the Year, Featured by App Store badges, plus stats badges (#1 App, 5M+ Downloads, 100K+ Reviews with star ratings) and review quote cards.

## Phase 7: Release Script Fix

**Problem:** `scripts/release.sh` hung at "Checking tools..."

**Root cause:** `source "$HOME/.cargo/env" 2>/dev/null || true` hangs under `set -e` when the file doesn't exist (Homebrew Rust install, no rustup).

**Fix:** Changed to `[ -f "$HOME/.cargo/env" ] && source "$HOME/.cargo/env" || true`

## Files Modified in appscreen

| File | Changes |
|------|---------|
| `app.js` | +1500 lines: badges, templates, patterns, color extraction, gradient text |
| `index.html` | +210 lines: badge UI, pattern controls, gradient text controls, template grid, extracted colors |
| `styles.css` | +185 lines: badge picker, template cards, extracted colors |
| `three-renderer.js` | Debug logging (minor) |
| `vendor/` | Three.js + GLTFLoader + OrbitControls bundled locally |
| `src-tauri/Cargo.toml` | Added tauri-plugin-updater |
| `src-tauri/tauri.conf.json` | Updater config, rename, version |
| `src-tauri/capabilities/default.json` | Added updater permission |
| `src-tauri/src/lib.rs` | Updater plugin init + update check on launch |
| `src-tauri/Entitlements.plist` | New: macOS code signing entitlements |
| `.github/workflows/tauri-build.yml` | Signing env vars, includeUpdaterJson |
| `scripts/release.sh` | Full build + sign + notarize + release script |
| `README.md` | Authorship, build instructions |
| `package.json` | Renamed, version bumped |

## Current State

- **Version:** 1.0.2
- **Repo:** github.com/barrault01/appscreen
- **Latest release:** https://github.com/barrault01/appscreen/releases/tag/v1.0.2
- **Signing:** No Developer ID certificate yet — app is unsigned
- **Pending:** Developer ID Application certificate needed for proper distribution signing
