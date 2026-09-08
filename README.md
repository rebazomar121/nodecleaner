<img width="1080" height="1080" alt="nodecleaner-hero (1)" src="https://github.com/user-attachments/assets/d7bc623e-9b7b-4a3a-a39e-3ffe3e4ffc3a" />


# NodeCleaner

A Python CLI tool that cleans junk files from Node.js, React Native, and Expo development on macOS.

## Features

- **System cache cleaning** — Xcode, npm, Yarn, pnpm, Bun, Gradle, CocoaPods, Metro, and more
- **Project scanning** — Finds `node_modules`, build outputs, and framework caches across your projects
- **App build finder** — Locates stray `.apk`, `.ipa`, and `.aab` files in Downloads, Documents, and Desktop so you can delete them in one go
- **Interactive selector** — Arrow keys to navigate, space to toggle, 'a' to select all
- **Safe deletion** — Type "yes" to confirm, with full summary of what will be removed
- **Junk only** — Every target is something a rebuild, reinstall, or the tool itself regenerates. See [What It Never Touches](#what-it-never-touches)
- **Zero dependencies** — Pure Python standard library, no `pip install` needed

## Installation

The recommended way is [pipx](https://pipx.pypa.io), which installs the `nodecleaner`
command into an isolated environment and puts it on your `PATH`:

```bash
# Install pipx once (if you don't have it)
brew install pipx && pipx ensurepath

# Install NodeCleaner straight from GitHub
pipx install git+https://github.com/rebazomar121/nodecleaner.git
```

Then run it from anywhere:

```bash
nodecleaner
```

To upgrade or remove later:

```bash
pipx upgrade nodecleaner
pipx uninstall nodecleaner
```

> Prefer `pip`? `pip install git+https://github.com/rebazomar121/nodecleaner.git`
> works too, but `pipx` keeps it isolated from your other projects.

### Run without installing

```bash
git clone https://github.com/rebazomar121/nodecleaner.git
cd nodecleaner
python3 -m nodecleaner          # from the repo root
```

## Usage

```bash
nodecleaner                # interactive menu
nodecleaner --dry-run      # scan & select, but delete nothing (safe preview)
nodecleaner --yes          # skip the final "type yes" confirmation
nodecleaner --version
nodecleaner --help
```

### Menu Options

| Option | Description |
|--------|-------------|
| **[1] Full Clean** | Scan both system caches and a projects directory |
| **[2] System Caches** | Scan only system-wide caches (Xcode, npm, Gradle, etc.) |
| **[3] Project Files** | Scan a directory for node_modules, build outputs, etc. |
| **[4] App Builds** | Find `.apk` / `.ipa` / `.aab` files in Downloads, Documents, Desktop (plus an optional extra folder) |
| **[5] About** | Show information about the tool |
| **[6] Exit** | Quit |

### Interactive Selector Controls

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate items |
| `Space` | Toggle selection |
| `a` | Select / deselect all |
| `Enter` | Confirm selection |
| `q` | Cancel and return to menu |

## What It Cleans

### System Caches

- Xcode DerivedData, Archives, caches, and documentation cache
- Xcode iOS / watchOS / tvOS **DeviceSupport** symbols (often 3–6 GB per OS version, re-downloaded on demand)
- SwiftUI preview and Interface Builder caches, iOS device logs
- iOS Simulator caches, temp files, and logs
- **Unavailable simulators** whose runtime was removed (deleted via `xcrun simctl delete`, so CoreSimulator stays consistent)
- npm, Yarn (v1 & v2+), pnpm, and Bun caches
- React Native packager, Metro bundler, Flipper, Detox, and legacy `.rncache`
- Gradle caches, wrapper dists, and daemon logs
- Android Studio caches and logs, Android SDK cache, **emulator quick-boot snapshots**
- Kotlin/Native toolchains (`~/.konan`)
- CocoaPods cache and spec repos
- Expo CLI, EAS CLI, and EAS local build temp
- Watchman, TypeScript, Swift PM, and ccache
- Cypress, Playwright, Puppeteer browser downloads
- Electron, node-gyp, nvm / fnm / Volta, Deno, Firebase, Prisma caches
- VS Code, Cursor, and JetBrains editor caches (indexes are rebuilt on next launch)

### Project-Level

- `node_modules` — Node.js dependencies
- `ios/Pods` — CocoaPods dependencies
- `vendor/bundle` — Ruby gems installed by bundler
- `ios/build`, `android/build`, `android/app/build` — Native build outputs
- `android/.gradle`, `android/.cxx`, `android/app/.cxx` — Project Gradle cache and NDK intermediates
- `.expo`, `.next`, `.nuxt`, `.output`, `.turbo`, `.vite`, `.angular`, `.parcel-cache`, `.svelte-kit`, `.nx`, `.docusaurus`, `.astro` — Framework caches and outputs
- `dist`, `build`, `out`, `web-build`, `storybook-static` — Build output
- `coverage`, `.nyc_output`, `.jest-cache`, `playwright-report`, `test-results`, `cypress/videos`, `cypress/screenshots` — Test artifacts
- Junk files: `.eslintcache`, `*.tsbuildinfo`, `*.hprof` (Java heap dumps), and `npm-debug.log*`, `yarn-error.log`, `yarn-debug.log*`, `pnpm-debug.log*`, `lerna-debug.log*`

### App Builds

- `.apk` — Android APK
- `.aab` — Android App Bundle
- `.ipa` — iOS IPA

Searched in `~/Downloads`, `~/Documents`, and `~/Desktop` by default. You can add one
extra folder when prompted. Hidden folders, `node_modules`, and symlinks are skipped.

## What It Never Touches

NodeCleaner only lists things that are recreated by a rebuild, a reinstall, or the tool
that owns them. It deliberately **does not** offer:

- Source code, git history, or anything inside `.git`
- Android emulator images (`~/.android/avd/*.avd` itself) — only their quick-boot snapshots
- The Android SDK, system images, or `~/Library/Android/sdk`
- Maven's `~/.m2` repository
- Xcode user schemes and breakpoints (`xcuserdata`)
- Yarn zero-install caches (`.yarn/cache`) that may be committed
- `.vercel`, `.netlify`, `.wrangler` — these hold project links and local dev state
- Committed JS bundles such as `ios/main.jsbundle`
- Xcode `.xip` or Android Studio `.dmg` installers in Downloads
- Symlinks — a symlinked target is skipped rather than followed or removed

You always pick items from a list and confirm with "yes" before anything is deleted.
Use `--dry-run` to preview.

## Requirements

- macOS (Linux works for the non-Apple paths)
- Python 3.8+
- No external packages

## Development

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e . pytest
pytest
```
