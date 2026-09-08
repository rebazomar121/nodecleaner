#!/usr/bin/env python3
"""NodeCleaner - Clean junk files from Node.js/React Native/Expo development on macOS."""

import enum
import fnmatch
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import termios
import threading
import time
import tty
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# 1. Constants & Config
# ─────────────────────────────────────────────────────────────────────────────

VERSION = "1.1.0"

# Runtime flags, set from CLI args in main().
DRY_RUN = False
ASSUME_YES = False


class Category(enum.Enum):
    XCODE = "Xcode"
    SIMULATOR = "iOS Simulator"
    NPM = "npm"
    YARN = "Yarn"
    BUN = "Bun"
    PNPM = "pnpm"
    REACT_NATIVE = "React Native"
    METRO = "Metro Bundler"
    GRADLE = "Gradle"
    EXPO = "Expo"
    COCOAPODS = "CocoaPods"
    SWIFT = "Swift"
    WATCHMAN = "Watchman"
    TYPESCRIPT = "TypeScript"
    CCACHE = "ccache"
    NODE_MODULES = "node_modules"
    IOS_BUILD = "iOS Build"
    ANDROID_BUILD = "Android Build"
    NEXT = "Next.js"
    NUXT = "Nuxt.js"
    DIST = "Build Output"
    TURBO = "Turborepo"
    CYPRESS = "Cypress"
    PLAYWRIGHT = "Playwright"
    ELECTRON = "Electron"
    NODE_GYP = "node-gyp"
    NVM = "nvm"
    DENO = "Deno"
    PUPPETEER = "Puppeteer"
    NX = "Nx"
    ANGULAR = "Angular"
    PARCEL = "Parcel"
    GATSBY = "Gatsby"
    SVELTEKIT = "SvelteKit"
    JEST = "Jest"
    FIREBASE = "Firebase"
    APP_BUILD = "App Build"
    ANDROID_STUDIO = "Android Studio"
    ANDROID_EMULATOR = "Android Emulator"
    KOTLIN = "Kotlin"
    DETOX = "Detox"
    IDE = "IDE Cache"
    RUBY = "Ruby Gems"
    VITE = "Vite"
    ESLINT = "ESLint"
    LOGS = "Logs"


@dataclass
class CleanupTarget:
    path: str
    description: str
    category: Category
    size: int = 0
    selected: bool = False
    # When set, this command is run instead of deleting `path` directly
    # (used for things like `xcrun simctl delete <udid>`).
    command: Optional[List[str]] = None


HOME = os.path.expanduser("~")
TMPDIR = tempfile.gettempdir()

SYSTEM_TARGETS = [
    (os.path.join(HOME, "Library/Developer/Xcode/DerivedData"), "Xcode derived data", Category.XCODE),
    (os.path.join(HOME, "Library/Developer/Xcode/Archives"), "Xcode archives", Category.XCODE),
    (os.path.join(HOME, "Library/Developer/CoreSimulator/Caches"), "iOS simulator caches", Category.SIMULATOR),
    (os.path.join(HOME, "Library/Developer/CoreSimulator/Temp"), "iOS simulator temp", Category.SIMULATOR),
    (os.path.join(HOME, "Library/Caches/com.apple.dt.Xcode"), "Xcode caches", Category.XCODE),
    (os.path.join(HOME, ".npm"), "npm cache", Category.NPM),
    (os.path.join(HOME, "Library/Caches/Yarn"), "Yarn v1 cache", Category.YARN),
    (os.path.join(HOME, ".yarn/berry/cache"), "Yarn v2+ cache", Category.YARN),
    (os.path.join(HOME, ".bun/install/cache"), "Bun cache", Category.BUN),
    (os.path.join(HOME, "Library/pnpm/store"), "pnpm store", Category.PNPM),
    (os.path.join(HOME, ".local/share/pnpm/store"), "pnpm store (alt)", Category.PNPM),
    (os.path.join(HOME, "Library/Caches/ccache"), "ccache", Category.CCACHE),
    (os.path.join(HOME, "Library/Caches/CocoaPods"), "CocoaPods cache", Category.COCOAPODS),
    (os.path.join(HOME, "Library/Caches/org.swift.swiftpm"), "Swift PM cache", Category.SWIFT),
    (os.path.join(HOME, ".gradle/caches"), "Gradle caches", Category.GRADLE),
    (os.path.join(HOME, ".expo"), "Expo CLI cache", Category.EXPO),
    (os.path.join(HOME, "Library/Caches/com.facebook.watchman"), "Watchman cache", Category.WATCHMAN),
    (os.path.join(HOME, ".cache/typescript"), "TypeScript cache", Category.TYPESCRIPT),
    # Testing tool browser caches
    (os.path.join(HOME, "Library/Caches/Cypress"), "Cypress binaries", Category.CYPRESS),
    (os.path.join(HOME, "Library/Caches/ms-playwright"), "Playwright browsers", Category.PLAYWRIGHT),
    (os.path.join(HOME, ".cache/puppeteer"), "Puppeteer browsers", Category.PUPPETEER),
    # Electron & native addon caches
    (os.path.join(HOME, "Library/Caches/electron"), "Electron binaries", Category.ELECTRON),
    (os.path.join(HOME, "Library/Caches/node-gyp"), "node-gyp headers", Category.NODE_GYP),
    (os.path.join(HOME, ".node-gyp"), "node-gyp headers (legacy)", Category.NODE_GYP),
    # Additional package manager caches
    (os.path.join(HOME, "Library/Caches/pnpm"), "pnpm metadata cache", Category.PNPM),
    (os.path.join(HOME, "Library/Caches/bun"), "Bun metadata cache", Category.BUN),
    # Node version manager caches
    (os.path.join(HOME, ".nvm/.cache"), "nvm download cache", Category.NVM),
    (os.path.join(HOME, "Library/Application Support/fnm"), "fnm Node versions", Category.NVM),
    (os.path.join(HOME, ".volta/cache"), "Volta download cache", Category.NVM),
    # Framework & tool caches
    (os.path.join(HOME, "Library/Caches/next-swc"), "Next.js SWC compiler", Category.NEXT),
    (os.path.join(HOME, "Library/Caches/eas-cli"), "EAS CLI cache", Category.EXPO),
    (os.path.join(HOME, "Library/Caches/deno"), "Deno cache", Category.DENO),
    (os.path.join(HOME, ".firebase"), "Firebase CLI cache", Category.FIREBASE),
    # Additional CocoaPods & Gradle paths
    (os.path.join(HOME, ".cocoapods/repos"), "CocoaPods spec repos", Category.COCOAPODS),
    (os.path.join(HOME, ".gradle/wrapper/dists"), "Gradle wrapper dists", Category.GRADLE),
    (os.path.join(HOME, ".gradle/daemon"), "Gradle daemon logs", Category.GRADLE),
    # Misc Node.js caches
    (os.path.join(HOME, "Library/Caches/checkpoint-nodejs"), "Node.js update checks", Category.NPM),
    (os.path.join(HOME, ".cache/prisma"), "Prisma query engines", Category.NPM),
    # Xcode device support & user caches — Xcode re-downloads / regenerates these
    (os.path.join(HOME, "Library/Developer/Xcode/iOS DeviceSupport"), "iOS device support symbols", Category.XCODE),
    (os.path.join(HOME, "Library/Developer/Xcode/watchOS DeviceSupport"), "watchOS device support symbols", Category.XCODE),
    (os.path.join(HOME, "Library/Developer/Xcode/tvOS DeviceSupport"), "tvOS device support symbols", Category.XCODE),
    (os.path.join(HOME, "Library/Developer/Xcode/UserData/Previews"), "SwiftUI preview caches", Category.XCODE),
    (os.path.join(HOME, "Library/Developer/Xcode/UserData/IB Support"), "Interface Builder caches", Category.XCODE),
    (os.path.join(HOME, "Library/Developer/Xcode/DocumentationCache"), "Xcode documentation cache", Category.XCODE),
    (os.path.join(HOME, "Library/Developer/Xcode/iOS Device Logs"), "iOS device logs", Category.XCODE),
    (os.path.join(HOME, "Library/Logs/CoreSimulator"), "iOS simulator logs", Category.SIMULATOR),
    # Android / Kotlin tooling caches
    (os.path.join(HOME, ".android/cache"), "Android SDK cache", Category.ANDROID_STUDIO),
    (os.path.join(HOME, ".android/build-cache"), "Android build cache (legacy)", Category.ANDROID_STUDIO),
    (os.path.join(HOME, ".konan"), "Kotlin/Native toolchains", Category.KOTLIN),
    # React Native tooling caches
    (os.path.join(HOME, ".flipper"), "Flipper cache", Category.REACT_NATIVE),
    (os.path.join(HOME, ".rncache"), "RN third-party cache (legacy)", Category.REACT_NATIVE),
    (os.path.join(HOME, "Library/Detox"), "Detox framework cache", Category.DETOX),
]

# Editor caches (indexes / GPU / extension downloads) — rebuilt automatically on next launch.
_EDITOR_CACHE_SUBDIRS = ("Cache", "CachedData", "CachedExtensionVSIXs", "Code Cache", "GPUCache")
SYSTEM_TARGETS += [
    (os.path.join(HOME, "Library/Application Support", app_dir, sub), f"{app_name} cache ({sub})", Category.IDE)
    for app_dir, app_name in (("Code", "VS Code"), ("Cursor", "Cursor"))
    for sub in _EDITOR_CACHE_SUBDIRS
]

# Glob patterns relative to HOME (for versioned / per-device directories).
HOME_PATTERNS = [
    ("Library/Caches/Google/AndroidStudio*", "Android Studio caches", Category.ANDROID_STUDIO),
    ("Library/Logs/Google/AndroidStudio*", "Android Studio logs", Category.ANDROID_STUDIO),
    ("Library/Caches/JetBrains/*", "JetBrains IDE caches", Category.IDE),
    (".android/avd/*.avd/snapshots", "Emulator quick-boot snapshots", Category.ANDROID_EMULATOR),
]

TMPDIR_PATTERNS = [
    ("react-native-packager-cache-*", "RN packager cache", Category.REACT_NATIVE),
    ("metro-bundler-cache-*", "Metro bundler cache", Category.METRO),
    ("metro-cache", "Metro cache", Category.METRO),
    ("haste-map-*", "Haste map cache", Category.REACT_NATIVE),
    ("v8-compile-cache-*", "V8 compile cache", Category.NPM),
    ("node-compile-cache*", "Node.js compile cache", Category.NPM),
    ("jest_*", "Jest test cache", Category.JEST),
    ("eas-build-local-*", "EAS local build temp", Category.EXPO),
]

PROJECT_SCAN_DIRS = [
    ("node_modules", "Node.js dependencies", Category.NODE_MODULES),
    (os.path.join("ios", "Pods"), "CocoaPods deps", Category.COCOAPODS),
    (os.path.join("ios", "build"), "iOS build output", Category.IOS_BUILD),
    (os.path.join("android", "build"), "Android build output", Category.ANDROID_BUILD),
    (os.path.join("android", "app", "build"), "Android app build", Category.ANDROID_BUILD),
    (".expo", "Expo cache", Category.EXPO),
    (".next", "Next.js build", Category.NEXT),
    (".nuxt", "Nuxt.js build", Category.NUXT),
    ("dist", "Build output", Category.DIST),
    (".turbo", "Turborepo cache", Category.TURBO),
    (".angular", "Angular CLI cache", Category.ANGULAR),
    (".parcel-cache", "Parcel bundler cache", Category.PARCEL),
    (".cache", "Build cache (Gatsby/Remix)", Category.GATSBY),
    (".svelte-kit", "SvelteKit build", Category.SVELTEKIT),
    (".nx", "Nx cache", Category.NX),
    ("coverage", "Test coverage reports", Category.JEST),
    ("build", "Build output", Category.DIST),
    ("out", "Build output", Category.DIST),
    ("storybook-static", "Storybook build", Category.DIST),
    # Android native intermediates & project-local Gradle cache
    (os.path.join("android", ".gradle"), "Android project Gradle cache", Category.ANDROID_BUILD),
    (os.path.join("android", ".cxx"), "Android NDK intermediates", Category.ANDROID_BUILD),
    (os.path.join("android", "app", ".cxx"), "Android NDK intermediates", Category.ANDROID_BUILD),
    # Ruby gems installed by bundler for iOS tooling
    (os.path.join("vendor", "bundle"), "Ruby gems (bundler)", Category.RUBY),
    # Test artifacts (videos, traces, reports)
    ("playwright-report", "Playwright HTML report", Category.PLAYWRIGHT),
    ("test-results", "Playwright test results", Category.PLAYWRIGHT),
    (os.path.join("cypress", "videos"), "Cypress videos", Category.CYPRESS),
    (os.path.join("cypress", "screenshots"), "Cypress screenshots", Category.CYPRESS),
    (".jest-cache", "Jest cache", Category.JEST),
    (".nyc_output", "NYC coverage output", Category.JEST),
    # More framework build outputs / caches
    (".output", "Nuxt 3 build output", Category.NUXT),
    ("web-build", "Expo web build", Category.EXPO),
    (".vite", "Vite cache", Category.VITE),
    (".docusaurus", "Docusaurus build cache", Category.DIST),
    (".astro", "Astro build cache", Category.DIST),
    (".rollup.cache", "Rollup cache", Category.DIST),
]

# Junk *files* (matched with fnmatch against the file name) found while scanning projects.
PROJECT_SCAN_FILES = [
    (".eslintcache", "ESLint cache", Category.ESLINT),
    ("*.tsbuildinfo", "TypeScript build info", Category.TYPESCRIPT),
    ("*.hprof", "Java heap dump", Category.ANDROID_BUILD),
    ("npm-debug.log*", "npm debug log", Category.LOGS),
    ("yarn-error.log", "Yarn error log", Category.LOGS),
    ("yarn-debug.log*", "Yarn debug log", Category.LOGS),
    ("pnpm-debug.log*", "pnpm debug log", Category.LOGS),
    ("lerna-debug.log*", "Lerna debug log", Category.LOGS),
]

# Directories to skip when walking the project tree
PRUNE_DIRS = {"node_modules", ".git", ".hg", ".svn", "__pycache__", ".Trash"}

# Mobile app build artifacts (.apk / .aab / .ipa) that pile up in user folders.
APP_BUILD_EXTENSIONS = {
    ".apk": "Android APK",
    ".aab": "Android App Bundle",
    ".ipa": "iOS IPA",
}
APP_BUILD_SCAN_DIRS = [
    os.path.join(HOME, "Downloads"),
    os.path.join(HOME, "Documents"),
    os.path.join(HOME, "Desktop"),
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Terminal UI
# ─────────────────────────────────────────────────────────────────────────────

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    if size_bytes < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            if unit == "B":
                return f"{size_bytes} B"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def print_banner():
    """Print the welcome banner."""
    banner = f"""{Colors.CYAN}{Colors.BOLD}
    ╔══════════════════════════════════════════════╗
    ║           NodeCleaner v{VERSION}               ║
    ║   Clean Node.js / React Native junk files    ║
    ║              for macOS                       ║
    ╚══════════════════════════════════════════════╝{Colors.RESET}
    """
    print(banner)


def progress_bar(current: int, total: int, width: int = 40, label: str = "") -> str:
    """Return a progress bar string."""
    if total == 0:
        pct = 1.0
    else:
        pct = min(current / total, 1.0)
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    pct_str = f"{pct * 100:.0f}%"
    return f"\r  {Colors.CYAN}[{bar}]{Colors.RESET} {pct_str} {label}"


class Spinner:
    """Animated spinner for long-running operations."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Scanning"):
        self.message = message
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, final_message: str = ""):
        self._running = False
        if self._thread:
            self._thread.join()
        # Clear line
        sys.stdout.write(f"\r{' ' * 80}\r")
        sys.stdout.flush()
        if final_message:
            print(f"  {Colors.GREEN}✓{Colors.RESET} {final_message}")

    def _spin(self):
        idx = 0
        while self._running:
            frame = self.FRAMES[idx % len(self.FRAMES)]
            sys.stdout.write(f"\r  {Colors.CYAN}{frame}{Colors.RESET} {self.message}...")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.08)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Scanner
# ─────────────────────────────────────────────────────────────────────────────

def _get_dir_size(path: str) -> int:
    """Calculate directory size using os.scandir (fast, no symlink follow)."""
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += _get_dir_size(entry.path)
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return total


def _add_dir_target(targets, seen, path, desc, cat) -> None:
    """Append a directory target if it exists, is not a symlink, is non-empty and unseen."""
    if os.path.islink(path) or not os.path.isdir(path):
        return
    real = os.path.realpath(path)
    if real in seen:
        return
    seen.add(real)
    size = _get_dir_size(path)
    if size > 0:
        targets.append(CleanupTarget(path=path, description=desc, category=cat, size=size))


def _runtime_label(runtime_id: str) -> str:
    """'com.apple.CoreSimulator.SimRuntime.iOS-16-4' -> 'iOS 16.4'."""
    tail = runtime_id.rsplit(".", 1)[-1]
    parts = tail.split("-")
    if len(parts) > 1:
        return f"{parts[0]} {'.'.join(parts[1:])}"
    return tail


def scan_unavailable_simulators() -> List[CleanupTarget]:
    """Find simulators whose runtime is no longer installed.

    These cannot be booted any more, so they are pure junk. They are removed
    with `xcrun simctl delete <udid>` rather than a raw directory delete so
    CoreSimulator's device registry stays consistent.
    """
    targets = []
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "-j"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode != 0:
            return targets
        data = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return targets

    for runtime_id, devices in data.get("devices", {}).items():
        for dev in devices:
            if dev.get("isAvailable", True):
                continue
            udid = dev.get("udid")
            if not udid:
                continue
            data_path = dev.get("dataPath") or ""
            size = _get_dir_size(data_path) if os.path.isdir(data_path) else 0
            name = dev.get("name", "Unknown device")
            targets.append(CleanupTarget(
                path=data_path or udid,
                description=f"Unavailable simulator: {name} ({_runtime_label(runtime_id)})",
                category=Category.SIMULATOR,
                size=size,
                command=["xcrun", "simctl", "delete", udid],
            ))
    return targets


def scan_system_caches() -> List[CleanupTarget]:
    """Scan fixed system cache paths, HOME/tmp glob patterns and unavailable simulators."""
    targets = []
    seen = set()

    # Fixed paths
    for path, desc, cat in SYSTEM_TARGETS:
        _add_dir_target(targets, seen, path, desc, cat)

    # Glob patterns under HOME and the temp dir
    for base, patterns in ((HOME, HOME_PATTERNS), (TMPDIR, TMPDIR_PATTERNS)):
        for pattern, desc, cat in patterns:
            for match in glob.glob(os.path.join(base, pattern)):
                _add_dir_target(targets, seen, match, desc, cat)

    # Simulators that can no longer be booted (runtime removed)
    targets.extend(scan_unavailable_simulators())

    targets.sort(key=lambda t: t.size, reverse=True)
    return targets


def scan_projects(base_dir: str) -> List[CleanupTarget]:
    """Scan a projects directory for cleanable targets using os.walk with pruning."""
    targets = []
    seen = set()
    base_dir = os.path.expanduser(base_dir)

    if not os.path.isdir(base_dir):
        return targets

    found_dirs = set()  # directories already reported as targets; never walk inside them

    for dirpath, dirnames, filenames in os.walk(base_dir, followlinks=False):
        if dirpath in found_dirs:
            dirnames[:] = []
            continue

        # Prune directories we don't want to walk into
        dirnames[:] = [
            d for d in dirnames
            if d not in PRUNE_DIRS and not d.startswith(".")
            or d in (".expo", ".next", ".nuxt", ".turbo", ".angular",
                     ".parcel-cache", ".cache", ".svelte-kit", ".nx")
        ]

        # Check each possible target directory
        for dirname, desc, cat in PROJECT_SCAN_DIRS:
            candidate = os.path.join(dirpath, dirname)
            if os.path.islink(candidate) or not os.path.isdir(candidate):
                continue
            real = os.path.realpath(candidate)
            if real in seen:
                continue
            seen.add(real)
            found_dirs.add(candidate)
            size = _get_dir_size(candidate)
            if size > 0:
                targets.append(CleanupTarget(
                    path=candidate, description=desc, category=cat, size=size
                ))

        # Check for junk files in this directory
        for name in filenames:
            for pattern, desc, cat in PROJECT_SCAN_FILES:
                if not fnmatch.fnmatch(name, pattern):
                    continue
                full = os.path.join(dirpath, name)
                try:
                    if os.path.islink(full) or not os.path.isfile(full):
                        break
                    size = os.path.getsize(full)
                except OSError:
                    break
                real = os.path.realpath(full)
                if real not in seen and size > 0:
                    seen.add(real)
                    targets.append(CleanupTarget(
                        path=full, description=desc, category=cat, size=size
                    ))
                break

        # Further prune: if we found node_modules here, don't go into it
        if "node_modules" in dirnames:
            dirnames.remove("node_modules")

    targets.sort(key=lambda t: t.size, reverse=True)
    return targets


def scan_app_builds(base_dirs: Optional[List[str]] = None) -> List[CleanupTarget]:
    """Find .apk / .aab / .ipa files under the given folders.

    Defaults to ~/Downloads, ~/Documents and ~/Desktop. Symlinks are never
    followed and hidden / VCS / node_modules directories are skipped.
    """
    targets = []
    seen = set()
    dirs = APP_BUILD_SCAN_DIRS if base_dirs is None else base_dirs

    for base in dirs:
        base = os.path.expanduser(base)
        if not os.path.isdir(base):
            continue

        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = [
                d for d in dirnames
                if d not in PRUNE_DIRS and not d.startswith(".")
            ]

            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext not in APP_BUILD_EXTENSIONS:
                    continue

                full = os.path.join(dirpath, name)
                try:
                    if os.path.islink(full) or not os.path.isfile(full):
                        continue
                    size = os.path.getsize(full)
                except OSError:
                    continue

                real = os.path.realpath(full)
                if real in seen:
                    continue
                seen.add(real)

                targets.append(CleanupTarget(
                    path=full,
                    description=APP_BUILD_EXTENSIONS[ext],
                    category=Category.APP_BUILD,
                    size=size,
                ))

    targets.sort(key=lambda t: t.size, reverse=True)
    return targets


# ─────────────────────────────────────────────────────────────────────────────
# 4. Interactive Selector
# ─────────────────────────────────────────────────────────────────────────────

class InteractiveSelector:
    """Raw terminal checkbox selector using tty/termios."""

    def __init__(self, targets: List[CleanupTarget]):
        self.targets = targets
        self.cursor = 0
        self.scroll_offset = 0
        self._old_settings = None

    def _get_terminal_height(self) -> int:
        try:
            return os.get_terminal_size().lines
        except OSError:
            return 24

    def _get_visible_rows(self) -> int:
        # Reserve lines for header (4) + footer (4)
        return max(self._get_terminal_height() - 8, 5)

    def _read_key(self) -> str:
        """Read a single keypress from raw terminal."""
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(1)
            if seq == "[":
                code = sys.stdin.read(1)
                if code == "A":
                    return "up"
                elif code == "B":
                    return "down"
            return "escape"
        elif ch == " ":
            return "space"
        elif ch in ("\r", "\n"):
            return "enter"
        elif ch == "a":
            return "a"
        elif ch == "q":
            return "q"
        elif ch == "\x03":  # Ctrl+C
            return "ctrl-c"
        return ch

    def _render(self):
        """Render the selector list."""
        visible = self._get_visible_rows()

        # Adjust scroll
        if self.cursor < self.scroll_offset:
            self.scroll_offset = self.cursor
        elif self.cursor >= self.scroll_offset + visible:
            self.scroll_offset = self.cursor - visible + 1

        total_size = sum(t.size for t in self.targets if t.selected)
        selected_count = sum(1 for t in self.targets if t.selected)

        # Move cursor up to redraw (clear previous render)
        lines_to_clear = visible + 4
        sys.stdout.write(f"\033[{lines_to_clear}A\033[J")

        # Header
        print(f"  {Colors.BOLD}Select items to clean:{Colors.RESET}  "
              f"({selected_count} selected, {Colors.YELLOW}{format_size(total_size)}{Colors.RESET})")
        print(f"  {Colors.DIM}↑/↓ navigate  SPACE toggle  'a' all  ENTER confirm  'q' cancel{Colors.RESET}")
        print()

        # Items
        end = min(self.scroll_offset + visible, len(self.targets))
        for i in range(self.scroll_offset, end):
            t = self.targets[i]
            is_cursor = i == self.cursor
            checkbox = f"{Colors.GREEN}■{Colors.RESET}" if t.selected else "□"
            prefix = f"{Colors.CYAN}▸{Colors.RESET}" if is_cursor else " "
            size_str = format_size(t.size)
            cat_str = f"{Colors.DIM}[{t.category.value}]{Colors.RESET}"

            # Shorten path for display (command targets show their description instead)
            display_path = t.description if t.command else t.path.replace(HOME, "~")
            if len(display_path) > 50:
                display_path = "..." + display_path[-47:]

            line = f"  {prefix} {checkbox}  {Colors.YELLOW}{size_str:>10}{Colors.RESET}  {display_path}  {cat_str}"
            if is_cursor:
                line = f"{Colors.BOLD}{line}{Colors.RESET}"
            print(line)

        # Pad remaining lines
        for _ in range(visible - (end - self.scroll_offset)):
            print()

        # Scroll indicator
        if len(self.targets) > visible:
            pos = f" ({self.scroll_offset + 1}-{end} of {len(self.targets)})"
        else:
            pos = ""
        print(f"  {Colors.DIM}{pos}{Colors.RESET}")

    def run(self) -> Optional[List[CleanupTarget]]:
        """Run interactive selection. Returns selected targets or None if cancelled."""
        if not self.targets:
            print(f"  {Colors.YELLOW}No items found to clean.{Colors.RESET}")
            return None

        # Setup raw terminal
        fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(fd)

        try:
            # Use cbreak mode: disable echo and canonical mode but keep output processing
            new = termios.tcgetattr(fd)
            new[3] &= ~(termios.ECHO | termios.ICANON)
            new[6][termios.VMIN] = 1
            new[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSAFLUSH, new)

            # Print initial frame space
            visible = self._get_visible_rows()
            for _ in range(visible + 4):
                print()

            self._render()

            while True:
                key = self._read_key()

                if key == "up":
                    self.cursor = max(0, self.cursor - 1)
                elif key == "down":
                    self.cursor = min(len(self.targets) - 1, self.cursor + 1)
                elif key == "space":
                    self.targets[self.cursor].selected = not self.targets[self.cursor].selected
                elif key == "a":
                    all_selected = all(t.selected for t in self.targets)
                    for t in self.targets:
                        t.selected = not all_selected
                elif key == "enter":
                    selected = [t for t in self.targets if t.selected]
                    return selected if selected else None
                elif key in ("q", "escape"):
                    return None
                elif key == "ctrl-c":
                    return None

                self._render()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_settings)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Cleaner
# ─────────────────────────────────────────────────────────────────────────────

def _rmtree_onerror(func, path, exc_info):
    """Error handler for shutil.rmtree - skip permission errors."""
    pass


def delete_targets(targets: List[CleanupTarget]) -> Tuple[int, int, int]:
    """Delete selected targets. Returns (success_count, fail_count, freed_bytes)."""
    success = 0
    failed = 0
    freed = 0
    total = len(targets)

    print()
    for i, target in enumerate(targets):
        label = target.description if target.command else target.path.replace(HOME, "~")
        if len(label) > 40:
            label = "..." + label[-37:]
        sys.stdout.write(progress_bar(i, total, label=label))
        sys.stdout.flush()

        try:
            if DRY_RUN:
                # Simulate: report what would be freed without touching disk.
                success += 1
                freed += target.size
                continue
            if target.command:
                # Tool-managed target (e.g. `xcrun simctl delete <udid>`).
                result = subprocess.run(
                    target.command, capture_output=True, text=True, timeout=300, check=False
                )
                if result.returncode == 0:
                    success += 1
                    freed += target.size
                else:
                    failed += 1
                continue
            if os.path.islink(target.path) or os.path.isfile(target.path):
                # Single file target (e.g. .apk / .ipa / .aab) — os.remove raises on failure.
                os.remove(target.path)
                success += 1
                freed += target.size
                continue
            shutil.rmtree(target.path, onerror=_rmtree_onerror)
            if not os.path.exists(target.path):
                success += 1
                freed += target.size
            else:
                # Partially deleted
                remaining = _get_dir_size(target.path)
                freed += target.size - remaining
                if remaining < target.size:
                    success += 1
                else:
                    failed += 1
        except Exception:
            failed += 1

    sys.stdout.write(progress_bar(total, total, label="Done!"))
    print()
    return success, failed, freed


def print_summary(success: int, failed: int, freed: int):
    """Print deletion summary."""
    print()
    print(f"  {Colors.BOLD}{'═' * 44}{Colors.RESET}")
    if DRY_RUN:
        print(f"  {Colors.BLUE}{Colors.BOLD}Dry Run Complete!{Colors.RESET}")
    else:
        print(f"  {Colors.GREEN}{Colors.BOLD}Cleanup Complete!{Colors.RESET}")
    print(f"  {Colors.BOLD}{'═' * 44}{Colors.RESET}")
    verb = "Would delete" if DRY_RUN else "Deleted"
    print(f"  {Colors.GREEN}✓ {verb}:{Colors.RESET}  {success} items")
    if failed > 0:
        print(f"  {Colors.RED}✗ Failed:{Colors.RESET}   {failed} items")
    freed_label = "Would free" if DRY_RUN else "Freed"
    print(f"  {Colors.CYAN}♻ {freed_label}:{Colors.RESET}    {Colors.BOLD}{format_size(freed)}{Colors.RESET}")
    print(f"  {Colors.BOLD}{'═' * 44}{Colors.RESET}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Main App
# ─────────────────────────────────────────────────────────────────────────────

def _restore_terminal():
    """Restore terminal to sane state using stty."""
    try:
        subprocess.run(["stty", "sane"], stdin=sys.stdin, check=False)
    except Exception:
        pass


class NodeCleaner:
    """Main application class."""

    def __init__(self):
        self.last_projects_dir = ""

    def run(self):
        """Main application loop."""
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._handle_sigint)

        print_banner()

        while True:
            choice = self._show_menu()

            if choice == "1":
                self._run_full_clean()
            elif choice == "2":
                self._run_system_clean()
            elif choice == "3":
                self._run_project_clean()
            elif choice == "4":
                self._run_app_build_clean()
            elif choice == "5":
                self._show_about()
            elif choice == "6":
                self._exit()
            else:
                print(f"  {Colors.RED}Invalid choice. Please try again.{Colors.RESET}")

    def _handle_sigint(self, sig, frame):
        """Handle Ctrl+C."""
        print(f"\n\n  {Colors.YELLOW}Interrupted. Goodbye!{Colors.RESET}\n")
        _restore_terminal()
        sys.exit(0)

    def _show_menu(self) -> str:
        """Display the main menu and get user choice."""
        print(f"  {Colors.BOLD}Main Menu{Colors.RESET}")
        print(f"  {'─' * 30}")
        print(f"  {Colors.CYAN}[1]{Colors.RESET} Full Clean (System + Projects)")
        print(f"  {Colors.CYAN}[2]{Colors.RESET} System Caches Only")
        print(f"  {Colors.CYAN}[3]{Colors.RESET} Project Files Only")
        print(f"  {Colors.CYAN}[4]{Colors.RESET} App Builds (.apk / .ipa / .aab)")
        print(f"  {Colors.CYAN}[5]{Colors.RESET} About")
        print(f"  {Colors.CYAN}[6]{Colors.RESET} Exit")
        print()

        try:
            choice = input(f"  {Colors.BOLD}Choose an option [1-6]:{Colors.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "6"
        print()
        return choice

    def _prompt_projects_dir(self) -> Optional[str]:
        """Prompt the user for a projects directory path."""
        default = self.last_projects_dir or os.path.join(HOME, "Documents")
        try:
            path = input(
                f"  {Colors.BOLD}Projects directory{Colors.RESET} [{Colors.DIM}{default}{Colors.RESET}]: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if not path:
            path = default

        path = os.path.expanduser(path)

        if not os.path.isdir(path):
            print(f"  {Colors.RED}Directory not found: {path}{Colors.RESET}")
            return None

        self.last_projects_dir = path
        return path

    def _scan_and_select(self, targets: List[CleanupTarget]) -> Optional[List[CleanupTarget]]:
        """Show interactive selector and confirm deletion."""
        if not targets:
            print(f"  {Colors.YELLOW}Nothing found to clean.{Colors.RESET}")
            print()
            return None

        total_size = sum(t.size for t in targets)
        print(f"  Found {Colors.BOLD}{len(targets)}{Colors.RESET} items "
              f"({Colors.YELLOW}{format_size(total_size)}{Colors.RESET} total)")
        print()

        selector = InteractiveSelector(targets)
        selected = selector.run()

        if not selected:
            print(f"\n  {Colors.YELLOW}Cancelled.{Colors.RESET}")
            print()
            return None

        return selected

    def _confirm_and_delete(self, selected: List[CleanupTarget]):
        """Show warning and confirm deletion."""
        total_size = sum(t.size for t in selected)

        print()
        if DRY_RUN:
            print(f"  {Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} DRY RUN {Colors.RESET}")
            print(f"  Would delete {Colors.BOLD}{len(selected)}{Colors.RESET} items "
                  f"({Colors.YELLOW}{format_size(total_size)}{Colors.RESET}) — nothing will be removed")
        else:
            print(f"  {Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} WARNING {Colors.RESET}")
            print(f"  You are about to delete {Colors.BOLD}{len(selected)}{Colors.RESET} items "
                  f"({Colors.YELLOW}{format_size(total_size)}{Colors.RESET})")
        print()

        # Show what will be deleted
        for t in selected[:10]:
            display_path = t.description if t.command else t.path.replace(HOME, "~")
            print(f"    {Colors.RED}•{Colors.RESET} {display_path}")
        if len(selected) > 10:
            print(f"    {Colors.DIM}... and {len(selected) - 10} more{Colors.RESET}")

        print()
        if not DRY_RUN:
            print(f"  {Colors.RED}{Colors.BOLD}This action cannot be undone!{Colors.RESET}")

        if ASSUME_YES or DRY_RUN:
            confirm = "yes"
        else:
            try:
                confirm = input(f"  Type {Colors.RED}{Colors.BOLD}yes{Colors.RESET} to confirm: ").strip()
            except (EOFError, KeyboardInterrupt):
                confirm = ""

        if confirm.lower() != "yes":
            print(f"\n  {Colors.YELLOW}Cancelled.{Colors.RESET}")
            print()
            return

        success, failed, freed = delete_targets(selected)
        print_summary(success, failed, freed)

    def _run_system_clean(self):
        """Run system caches cleanup."""
        print(f"  {Colors.BOLD}Scanning system caches...{Colors.RESET}")
        spinner = Spinner("Scanning system caches")
        spinner.start()
        targets = scan_system_caches()
        spinner.stop(f"Found {len(targets)} cache locations")

        selected = self._scan_and_select(targets)
        if selected:
            self._confirm_and_delete(selected)

    def _run_project_clean(self):
        """Run project files cleanup."""
        projects_dir = self._prompt_projects_dir()
        if not projects_dir:
            print()
            return

        print()
        print(f"  {Colors.BOLD}Scanning projects in {projects_dir}...{Colors.RESET}")
        spinner = Spinner(f"Scanning {projects_dir}")
        spinner.start()
        targets = scan_projects(projects_dir)
        spinner.stop(f"Found {len(targets)} cleanable directories")

        selected = self._scan_and_select(targets)
        if selected:
            self._confirm_and_delete(selected)

    def _run_app_build_clean(self):
        """Find and remove .apk / .ipa / .aab files from Downloads, Documents, Desktop."""
        dirs = [d for d in APP_BUILD_SCAN_DIRS if os.path.isdir(d)]

        # Optional extra folder on top of the defaults.
        try:
            extra = input(
                f"  {Colors.BOLD}Extra folder to scan{Colors.RESET} "
                f"[{Colors.DIM}ENTER to skip{Colors.RESET}]: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if extra:
            extra = os.path.expanduser(extra)
            if not os.path.isdir(extra):
                print(f"  {Colors.RED}Directory not found: {extra}{Colors.RESET}")
                print()
                return
            if extra not in dirs:
                dirs.append(extra)

        if not dirs:
            print(f"  {Colors.YELLOW}No folders to scan.{Colors.RESET}")
            print()
            return

        labels = ", ".join(d.replace(HOME, "~") for d in dirs)
        print()
        print(f"  {Colors.BOLD}Scanning for app builds in {labels}...{Colors.RESET}")
        spinner = Spinner("Scanning for .apk / .ipa / .aab files")
        spinner.start()
        targets = scan_app_builds(dirs)
        spinner.stop(f"Found {len(targets)} app build files")

        selected = self._scan_and_select(targets)
        if selected:
            self._confirm_and_delete(selected)

    def _run_full_clean(self):
        """Run both system and project cleanup."""
        projects_dir = self._prompt_projects_dir()
        if not projects_dir:
            print()
            return

        print()
        spinner = Spinner("Scanning system caches and projects")
        spinner.start()
        system_targets = scan_system_caches()
        project_targets = scan_projects(projects_dir)
        all_targets = system_targets + project_targets

        # Dedup by realpath
        seen = set()
        deduped = []
        for t in all_targets:
            real = os.path.realpath(t.path)
            if real not in seen:
                seen.add(real)
                deduped.append(t)
        deduped.sort(key=lambda t: t.size, reverse=True)

        spinner.stop(f"Found {len(deduped)} items")

        selected = self._scan_and_select(deduped)
        if selected:
            self._confirm_and_delete(selected)

    def _show_about(self):
        """Show about information."""
        print(f"  {Colors.BOLD}NodeCleaner v{VERSION}{Colors.RESET}")
        print(f"  {Colors.DIM}{'─' * 40}{Colors.RESET}")
        print(f"  A CLI tool to clean junk files from")
        print(f"  Node.js, React Native, and Expo")
        print(f"  development on macOS.")
        print()
        print(f"  {Colors.BOLD}What it cleans:{Colors.RESET}")
        print(f"    • Xcode derived data & caches")
        print(f"    • iOS Simulator caches")
        print(f"    • npm, Yarn, pnpm, Bun caches")
        print(f"    • Metro bundler & React Native caches")
        print(f"    • Gradle caches")
        print(f"    • CocoaPods caches")
        print(f"    • node_modules directories")
        print(f"    • Build outputs (ios/build, android/build, dist)")
        print(f"    • Framework caches (.next, .nuxt, .expo, .turbo)")
        print(f"    • Angular, Parcel, SvelteKit, Gatsby, Nx caches")
        print(f"    • Cypress, Playwright, Puppeteer browser caches")
        print(f"    • Electron & node-gyp build caches")
        print(f"    • nvm, fnm, Volta version manager caches")
        print(f"    • Deno, Firebase CLI, Prisma caches")
        print(f"    • Jest, Storybook, coverage outputs")
        print(f"    • Xcode device support symbols, previews & logs")
        print(f"    • Unavailable iOS simulators (runtime removed)")
        print(f"    • Android Studio caches, emulator snapshots, NDK .cxx")
        print(f"    • Kotlin/Native, Flipper, Detox tool caches")
        print(f"    • VS Code, Cursor, JetBrains editor caches")
        print(f"    • Playwright / Cypress reports, videos, screenshots")
        print(f"    • Stray logs, .eslintcache, *.tsbuildinfo, *.hprof")
        print(f"    • .apk / .ipa / .aab app builds in Downloads, Documents, Desktop")
        print()
        print(f"  {Colors.BOLD}Never touched:{Colors.RESET} source code, emulator images,")
        print(f"  Android SDK, ~/.m2, Xcode user schemes/breakpoints, .vercel/.netlify")
        print(f"  project links, or anything that cannot be regenerated by a rebuild.")
        print()
        print(f"  {Colors.DIM}Pure Python — no external dependencies{Colors.RESET}")
        print()

    def _exit(self):
        """Exit the application."""
        print(f"  {Colors.GREEN}Goodbye!{Colors.RESET}\n")
        sys.exit(0)


def main(argv: Optional[List[str]] = None):
    import argparse

    parser = argparse.ArgumentParser(
        prog="nodecleaner",
        description="Clean junk files from Node.js / React Native / Expo development on macOS.",
    )
    parser.add_argument(
        "--version", action="version", version=f"NodeCleaner {VERSION}"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and select normally, but do not delete anything (report what would be freed).",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the final 'type yes to confirm' prompt before deleting.",
    )
    args = parser.parse_args(argv)

    global DRY_RUN, ASSUME_YES
    DRY_RUN = args.dry_run
    ASSUME_YES = args.yes

    if sys.platform != "darwin":
        print("Warning: NodeCleaner is designed for macOS. Some paths may not exist on your system.")

    app = NodeCleaner()
    app.run()


if __name__ == "__main__":
    main()
