#!/usr/bin/env python3
"""
Generate .appscreen project folders from benefit/screenshot data.

Creates a folder-based .appscreen project that can be opened in the
App Store Screenshot Generator (appscreen) Tauri desktop app.

Supports fastlane directory structures natively — can scan
fastlane/screenshots/ for localized images and fastlane/metadata/
for app descriptions and keywords.

Usage:
    # From benefits JSON + explicit screenshots
    python3 generate_appscreen.py \
        --name "My App Screenshots" \
        --bg "#E31837" \
        --device iphone-6.9 \
        --benefits benefits.json \
        --output my-app.appscreen

    # From inline benefits
    python3 generate_appscreen.py \
        --name "My App" \
        --bg "#E31837" \
        --benefit "TRACK" "CARD PRICES" screenshot1.png \
        --benefit "SEARCH" "ANY CARD" screenshot2.png \
        --output my-app.appscreen

    # From fastlane directory (auto-discovers screenshots + metadata)
    python3 generate_appscreen.py \
        --name "My App" \
        --bg "#E31837" \
        --fastlane ./fastlane \
        --benefits benefits.json \
        --output my-app.appscreen

benefits.json format:
    [
        {
            "verb": "TRACK",
            "desc": "CARD PRICES",
            "fastlane_index": 1,
            "translations": {
                "fr": {"verb": "SUIVEZ", "desc": "LES PRIX"},
                "de": {"verb": "VERFOLGE", "desc": "KARTENPREISE"}
            }
        },
        ...
    ]

Fields:
  - "verb" / "desc": default headline/subheadline (English fallback)
  - "translations": per-language overrides (missing languages use verb/desc)
  - "screenshot": explicit image path (takes priority)
  - "fastlane_index": 1-based index into the fastlane screenshot list
  - "fastlane_pattern": regex pattern to match within fastlane screenshots
"""

import argparse
import base64
import glob as globmod
import json
import os
import re
import shutil
import sys


# Device presets matching appscreen's device list
DEVICE_DIMENSIONS = {
    "iphone-6.9": (1320, 2868),
    "iphone-6.7": (1290, 2796),
    "iphone-6.5": (1242, 2688),
    "iphone-6.1": (1179, 2556),
    "iphone-5.5": (1242, 2208),
    "ipad-13": (2064, 2752),
    "ipad-12.9": (2048, 2732),
    "ipad-11": (1668, 2388),
    "watch-ultra": (410, 502),
    "watch-46": (396, 484),
    "watch-42": (374, 448),
    "watch-44": (368, 448),
}

# Fastlane locale to appscreen language code mapping
FASTLANE_LOCALE_MAP = {
    "en-US": "en", "en-GB": "en-gb", "en-AU": "en-au", "en-CA": "en-ca",
    "fr-FR": "fr", "fr-CA": "fr-ca",
    "de-DE": "de", "es-ES": "es", "es-MX": "es-mx",
    "it": "it", "pt-BR": "pt-br", "pt-PT": "pt",
    "ja": "ja", "ko": "ko", "zh-Hans": "zh", "zh-Hant": "zh-tw",
    "nl-NL": "nl", "sv": "sv", "da": "da", "fi": "fi", "nb": "nb",
    "ru": "ru", "pl": "pl", "tr": "tr", "ar-SA": "ar",
    "th": "th", "vi": "vi", "id": "id", "ms": "ms",
    "hi": "hi", "uk": "uk", "cs": "cs", "el": "el",
    "he": "he", "hu": "hu", "ro": "ro", "sk": "sk",
    "ca": "ca", "hr": "hr",
}

# Map fastlane device names to appscreen device presets
FASTLANE_DEVICE_MAP = {
    "iphone 16 pro max": "iphone-6.9",
    "iphone 15 pro max": "iphone-6.7",
    "iphone 14 plus": "iphone-6.5",
    "iphone 14 pro max": "iphone-6.7",
    "iphone 13 pro max": "iphone-6.7",
    "iphone 8 plus": "iphone-5.5",
    "iphone se": "iphone-5.5",
    "ipad pro (12.9-inch)": "ipad-12.9",
    "ipad pro (13-inch)": "ipad-13",
    "ipad air (11-inch)": "ipad-11",
}


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def make_text_settings(verb, desc, languages=None, translations=None,
                       headline_size=100, subheadline_size=50):
    """Create text settings for a screenshot, optionally with multiple languages.

    Args:
        verb: Default headline text (used as fallback for all languages)
        desc: Default subheadline text (used as fallback for all languages)
        languages: List of language codes
        translations: Dict of {lang_code: {"verb": "...", "desc": "..."}} for per-language text
    """
    headline = verb.upper()
    subheadline = desc.upper()

    langs = languages or ["en"]
    first_lang = langs[0]
    translations = translations or {}

    headlines = {}
    subheadlines = {}
    for lang in langs:
        t = translations.get(lang, {})
        headlines[lang] = t.get("verb", headline).upper()
        subheadlines[lang] = t.get("desc", subheadline).upper()
    language_settings = {}
    for lang in langs:
        language_settings[lang] = {
            "headlineSize": headline_size,
            "subheadlineSize": subheadline_size,
            "position": "top",
            "offsetY": 12,
            "lineHeight": 110,
        }

    return {
        "headlineEnabled": True,
        "headlines": headlines,
        "headlineLanguages": langs,
        "currentHeadlineLang": first_lang,
        "headlineFont": "-apple-system, BlinkMacSystemFont, 'SF Pro Display'",
        "headlineSize": headline_size,
        "headlineWeight": "800",
        "headlineItalic": False,
        "headlineUnderline": False,
        "headlineStrikethrough": False,
        "headlineColor": "#ffffff",
        "perLanguageLayout": False,
        "languageSettings": language_settings,
        "currentLayoutLang": first_lang,
        "position": "top",
        "offsetY": 12,
        "lineHeight": 110,
        "subheadlineEnabled": True,
        "subheadlines": subheadlines,
        "subheadlineLanguages": langs,
        "currentSubheadlineLang": first_lang,
        "subheadlineFont": "-apple-system, BlinkMacSystemFont, 'SF Pro Display'",
        "subheadlineSize": subheadline_size,
        "subheadlineWeight": "400",
        "subheadlineItalic": False,
        "subheadlineUnderline": False,
        "subheadlineStrikethrough": False,
        "subheadlineColor": "#ffffff",
        "subheadlineOpacity": 70,
    }


def make_background(bg_hex):
    """Create a solid color background setting."""
    return {
        "type": "solid",
        "gradient": {
            "angle": 135,
            "stops": [
                {"color": bg_hex, "position": 0},
                {"color": bg_hex, "position": 100},
            ],
        },
        "solid": bg_hex,
        "image": None,
        "imageFit": "cover",
        "imageBlur": 0,
        "overlayColor": "#000000",
        "overlayOpacity": 0,
        "noise": False,
        "noiseIntensity": 10,
    }


def make_screenshot_settings():
    """Create default screenshot positioning settings."""
    return {
        "scale": 70,
        "y": 60,
        "x": 50,
        "rotation": 0,
        "perspective": 0,
        "cornerRadius": 24,
        "use3D": False,
        "device3D": "iphone",
        "rotation3D": {"x": 0, "y": 0, "z": 0},
        "shadow": {
            "enabled": True,
            "color": "#000000",
            "blur": 40,
            "opacity": 30,
            "x": 0,
            "y": 20,
        },
        "frame": {
            "enabled": False,
            "color": "#1d1d1f",
            "width": 12,
            "opacity": 100,
        },
    }


def scan_fastlane_screenshots(fastlane_dir):
    """
    Scan fastlane/screenshots/ directory and return structured data.

    Returns:
        {
            "languages": ["en-US", "de-DE", ...],
            "devices": {"iPhone 16 Pro Max": "iphone-6.9", ...},
            "screenshots": {
                "base_name": {
                    "en-US": "/path/to/en-US/iPhone 16 Pro Max-01_Main.png",
                    "de-DE": "/path/to/de-DE/iPhone 16 Pro Max-01_Main.png",
                },
                ...
            },
            "ordered": ["01_Main", "02_Features", ...],
        }
    """
    screenshots_dir = os.path.join(fastlane_dir, "screenshots")
    if not os.path.isdir(screenshots_dir):
        return None

    result = {
        "languages": [],
        "devices": {},
        "screenshots": {},
        "ordered": [],
        "files_by_lang": {},
    }

    # Scan language directories
    for entry in sorted(os.listdir(screenshots_dir)):
        lang_dir = os.path.join(screenshots_dir, entry)
        if not os.path.isdir(lang_dir):
            continue
        # Skip non-locale directories
        if not re.match(r"^[a-z]{2}(-[A-Za-z]{2,4})?$", entry):
            continue

        result["languages"].append(entry)
        result["files_by_lang"][entry] = []

        for img_file in sorted(os.listdir(lang_dir)):
            if not img_file.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            full_path = os.path.join(lang_dir, img_file)
            result["files_by_lang"][entry].append(full_path)

            # Parse fastlane naming: "Device Name-01_ScreenName.png"
            match = re.match(r"^(.+?)-(\d+)[-_](.+)\.(png|jpg|jpeg)$", img_file, re.IGNORECASE)
            if match:
                device_name = match.group(1)
                seq_num = match.group(2)
                screen_name = match.group(3)
                base_name = f"{seq_num}_{screen_name}"

                # Map device
                device_lower = device_name.lower().strip()
                if device_lower not in result["devices"]:
                    for key, val in FASTLANE_DEVICE_MAP.items():
                        if key in device_lower:
                            result["devices"][device_lower] = val
                            break

                # Group by base name across languages
                if base_name not in result["screenshots"]:
                    result["screenshots"][base_name] = {}
                    result["ordered"].append(base_name)
                result["screenshots"][base_name][entry] = full_path
            else:
                # Non-standard naming — use filename as base
                base = os.path.splitext(img_file)[0]
                if base not in result["screenshots"]:
                    result["screenshots"][base] = {}
                    result["ordered"].append(base)
                result["screenshots"][base][entry] = full_path

    return result


def scan_fastlane_metadata(fastlane_dir):
    """
    Scan fastlane/metadata/ directory for app metadata.

    Returns:
        {
            "en-US": {
                "name": "My App",
                "subtitle": "Do amazing things",
                "description": "Full description...",
                "keywords": "keyword1,keyword2",
                "promotional_text": "...",
                "release_notes": "..."
            },
            ...
        }
    """
    metadata_dir = os.path.join(fastlane_dir, "metadata")
    if not os.path.isdir(metadata_dir):
        return None

    result = {}
    metadata_files = [
        "name.txt", "subtitle.txt", "description.txt",
        "keywords.txt", "promotional_text.txt", "release_notes.txt",
    ]

    for entry in sorted(os.listdir(metadata_dir)):
        lang_dir = os.path.join(metadata_dir, entry)
        if not os.path.isdir(lang_dir):
            continue
        if not re.match(r"^[a-z]{2}(-[A-Za-z]{2,4})?$", entry):
            continue

        lang_data = {}
        for mf in metadata_files:
            fpath = os.path.join(lang_dir, mf)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    lang_data[mf.replace(".txt", "")] = f.read().strip()

        if lang_data:
            result[entry] = lang_data

    return result


def resolve_fastlane_screenshot(benefit, fastlane_data, primary_lang):
    """
    Resolve a screenshot path for a benefit using fastlane data.

    Checks: explicit screenshot path > fastlane_index > fastlane_pattern
    """
    # Explicit path takes priority
    if benefit.get("screenshot") and os.path.exists(benefit["screenshot"]):
        return benefit["screenshot"]

    if not fastlane_data:
        return benefit.get("screenshot")

    ordered = fastlane_data["ordered"]

    # By index (1-based)
    idx = benefit.get("fastlane_index")
    if idx and 1 <= idx <= len(ordered):
        base_name = ordered[idx - 1]
        lang_files = fastlane_data["screenshots"].get(base_name, {})
        return lang_files.get(primary_lang) or next(iter(lang_files.values()), None)

    # By pattern
    pattern = benefit.get("fastlane_pattern")
    if pattern:
        for base_name in ordered:
            if re.search(pattern, base_name, re.IGNORECASE):
                lang_files = fastlane_data["screenshots"].get(base_name, {})
                return lang_files.get(primary_lang) or next(iter(lang_files.values()), None)

    return benefit.get("screenshot")


def generate_appscreen(project_name, bg_hex, device, benefits, output_path,
                       fastlane_dir=None, languages=None):
    """
    Generate an .appscreen project folder.

    Args:
        project_name: Display name of the project
        bg_hex: Background color hex (e.g., "#E31837")
        device: Device preset key (e.g., "iphone-6.9")
        benefits: List of dicts with keys: verb, desc, screenshot/fastlane_index
        output_path: Output .appscreen folder path
        fastlane_dir: Optional path to fastlane/ directory
        languages: Optional list of language codes to include
    """
    dimensions = DEVICE_DIMENSIONS.get(device, (1320, 2868))

    # Scan fastlane if provided
    fastlane_screenshots = None
    fastlane_metadata = None
    if fastlane_dir:
        fastlane_screenshots = scan_fastlane_screenshots(fastlane_dir)
        fastlane_metadata = scan_fastlane_metadata(fastlane_dir)

        if fastlane_screenshots:
            print(f"Found fastlane screenshots: {len(fastlane_screenshots['ordered'])} screens, "
                  f"{len(fastlane_screenshots['languages'])} languages")
        if fastlane_metadata:
            print(f"Found fastlane metadata: {list(fastlane_metadata.keys())}")

    # Determine languages
    project_languages = ["en"]
    if languages:
        project_languages = languages
    elif fastlane_screenshots:
        project_languages = []
        for fl_locale in fastlane_screenshots["languages"]:
            lang_code = FASTLANE_LOCALE_MAP.get(fl_locale, fl_locale.split("-")[0].lower())
            if lang_code not in project_languages:
                project_languages.append(lang_code)
        if not project_languages:
            project_languages = ["en"]

    primary_fastlane_lang = None
    if fastlane_screenshots and fastlane_screenshots["languages"]:
        if "en-US" in fastlane_screenshots["languages"]:
            primary_fastlane_lang = "en-US"
        else:
            primary_fastlane_lang = fastlane_screenshots["languages"][0]

    # Ensure output path ends with .appscreen
    if not output_path.endswith(".appscreen"):
        output_path += ".appscreen"

    # Create the project folder
    os.makedirs(output_path, exist_ok=True)
    images_dir = os.path.join(output_path, "images")
    os.makedirs(images_dir, exist_ok=True)

    image_index = 0

    def copy_image(src_path):
        """Copy an image file into the project folder and return its relative path."""
        nonlocal image_index
        ext = os.path.splitext(src_path)[1].lower() or ".png"
        rel_path = f"images/img_{image_index}{ext}"
        image_index += 1
        shutil.copy2(src_path, os.path.join(output_path, rel_path))
        return rel_path

    screenshots_data = []

    for i, benefit in enumerate(benefits):
        verb = benefit["verb"]
        desc = benefit["desc"]

        screenshot_path = resolve_fastlane_screenshot(
            benefit, fastlane_screenshots, primary_fastlane_lang
        )

        localized_images = {}

        if fastlane_screenshots and benefit.get("fastlane_index"):
            idx = benefit["fastlane_index"]
            ordered = fastlane_screenshots["ordered"]
            if 1 <= idx <= len(ordered):
                base_name = ordered[idx - 1]
                lang_files = fastlane_screenshots["screenshots"].get(base_name, {})

                for fl_locale, img_path in lang_files.items():
                    if os.path.exists(img_path):
                        lang_code = FASTLANE_LOCALE_MAP.get(
                            fl_locale, fl_locale.split("-")[0].lower()
                        )
                        img_filename = os.path.basename(img_path)
                        rel_path = copy_image(img_path)
                        localized_images[lang_code] = {
                            "imagePath": rel_path,
                            "name": img_filename,
                        }

        elif fastlane_screenshots and benefit.get("fastlane_pattern"):
            pattern = benefit["fastlane_pattern"]
            for base_name in fastlane_screenshots["ordered"]:
                if re.search(pattern, base_name, re.IGNORECASE):
                    lang_files = fastlane_screenshots["screenshots"].get(base_name, {})
                    for fl_locale, img_path in lang_files.items():
                        if os.path.exists(img_path):
                            lang_code = FASTLANE_LOCALE_MAP.get(
                                fl_locale, fl_locale.split("-")[0].lower()
                            )
                            img_filename = os.path.basename(img_path)
                            rel_path = copy_image(img_path)
                            localized_images[lang_code] = {
                                "imagePath": rel_path,
                                "name": img_filename,
                            }
                    break

        elif screenshot_path and os.path.exists(screenshot_path):
            img_filename = os.path.basename(screenshot_path)
            rel_path = copy_image(screenshot_path)
            localized_images["en"] = {
                "imagePath": rel_path,
                "name": img_filename,
            }

        # Fill missing languages with fallback (primary language, or first available)
        if localized_images:
            first_lang = project_languages[0]
            fallback = localized_images.get(first_lang) or next(iter(localized_images.values()))
            for lang in project_languages:
                if lang not in localized_images:
                    localized_images[lang] = dict(fallback)

        screenshots_data.append(
            {
                "name": benefit.get("name", f"{verb} {desc}"),
                "deviceType": None,
                "localizedImages": localized_images,
                "background": make_background(bg_hex),
                "screenshot": make_screenshot_settings(),
                "text": make_text_settings(verb, desc, languages=project_languages,
                                           translations=benefit.get("translations")),
                "elements": [],
                "popouts": [],
                "overrides": {},
            }
        )

    defaults = {
        "background": make_background(bg_hex),
        "screenshot": make_screenshot_settings(),
        "text": make_text_settings("", "", languages=project_languages),
        "elements": [],
        "popouts": [],
    }

    manifest = {
        "appscreen": 1,
        "projectName": project_name,
        "formatVersion": 2,
        "outputDevice": device,
        "customWidth": dimensions[0],
        "customHeight": dimensions[1],
        "currentLanguage": project_languages[0],
        "projectLanguages": project_languages,
        "selectedIndex": 0,
        "defaults": defaults,
        "screenshots": screenshots_data,
    }

    manifest_path = os.path.join(output_path, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    lang_info = f", {len(project_languages)} languages" if len(project_languages) > 1 else ""
    print(f"Created {output_path} ({len(benefits)} screenshots, {device}{lang_info})")


def main():
    p = argparse.ArgumentParser(
        description="Generate .appscreen project files for App Store Screenshot Generator"
    )
    p.add_argument("--name", required=True, help="Project name")
    p.add_argument("--bg", required=True, help="Background hex colour (#E31837)")
    p.add_argument(
        "--device",
        default="iphone-6.9",
        choices=list(DEVICE_DIMENSIONS.keys()),
        help="Target device (default: iphone-6.9)",
    )
    p.add_argument(
        "--benefits",
        help="Path to benefits JSON file",
    )
    p.add_argument(
        "--benefit",
        nargs=3,
        action="append",
        metavar=("VERB", "DESC", "SCREENSHOT"),
        help="Add a benefit: --benefit VERB DESC screenshot.png (repeatable)",
    )
    p.add_argument(
        "--fastlane",
        help="Path to fastlane/ directory (scans screenshots/ and metadata/)",
    )
    p.add_argument(
        "--languages",
        help="Comma-separated language codes to include (default: auto-detect from fastlane)",
    )
    p.add_argument("--output", required=True, help="Output .appscreen folder path")

    # Scan-only mode for discovery
    p.add_argument(
        "--scan",
        action="store_true",
        help="Scan fastlane directory and print discovery report (no output generated)",
    )

    args = p.parse_args()

    # Parse languages
    languages = None
    if args.languages:
        languages = [l.strip() for l in args.languages.split(",")]

    # Scan-only mode
    if args.scan:
        if not args.fastlane:
            print("Error: --scan requires --fastlane", file=sys.stderr)
            sys.exit(1)
        fl_screenshots = scan_fastlane_screenshots(args.fastlane)
        fl_metadata = scan_fastlane_metadata(args.fastlane)

        print("=== Fastlane Discovery Report ===\n")

        if fl_metadata:
            print("METADATA:")
            for locale, data in fl_metadata.items():
                print(f"  {locale}:")
                for key, val in data.items():
                    preview = val[:80] + "..." if len(val) > 80 else val
                    preview = preview.replace("\n", " ")
                    print(f"    {key}: {preview}")
            print()

        if fl_screenshots:
            print(f"SCREENSHOTS: {len(fl_screenshots['ordered'])} unique screens")
            print(f"LANGUAGES: {', '.join(fl_screenshots['languages'])}")
            print(f"DEVICES: {', '.join(fl_screenshots['devices'].keys())}")
            print()
            print("SCREENS:")
            for idx, base_name in enumerate(fl_screenshots["ordered"], 1):
                lang_files = fl_screenshots["screenshots"][base_name]
                langs = ", ".join(sorted(lang_files.keys()))
                print(f"  {idx}. {base_name} [{langs}]")
        else:
            print("No fastlane screenshots found.")

        sys.exit(0)

    benefits = []

    if args.benefits:
        with open(args.benefits) as f:
            benefits = json.load(f)

    if args.benefit:
        for verb, desc, screenshot in args.benefit:
            benefits.append(
                {"verb": verb, "desc": desc, "screenshot": screenshot}
            )

    if not benefits:
        print("Error: No benefits provided. Use --benefits or --benefit.", file=sys.stderr)
        sys.exit(1)

    generate_appscreen(
        args.name, args.bg, args.device, benefits, args.output,
        fastlane_dir=args.fastlane, languages=languages,
    )


if __name__ == "__main__":
    main()
