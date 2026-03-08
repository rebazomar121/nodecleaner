# NodeCleaner

A Python CLI tool that cleans junk files from Node.js, React Native, and Expo development on macOS.

## Features

- **System cache cleaning** — Xcode, npm, Yarn, pnpm, Bun, Gradle, CocoaPods, Metro, and more
- **Project scanning** — Finds `node_modules`, build outputs, and framework caches across your projects
- **Interactive selector** — Arrow keys to navigate, space to toggle, 'a' to select all
- **Safe deletion** — Type "yes" to confirm, with full summary of what will be removed
- **Zero dependencies** — Pure Python standard library, no `pip install` needed

## Usage

```bash
python3 nodecleaner.py
```

### Menu Options

| Option | Description |
|--------|-------------|
| **[1] Full Clean** | Scan both system caches and a projects directory |
| **[2] System Caches** | Scan only system-wide caches (Xcode, npm, Gradle, etc.) |
| **[3] Project Files** | Scan a directory for node_modules, build outputs, etc. |
| **[4] About** | Show information about the tool |
| **[5] Exit** | Quit |

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

- Xcode DerivedData, Archives, and caches
- iOS Simulator caches and temp files
- npm, Yarn (v1 & v2+), pnpm, and Bun caches
- React Native packager and Metro bundler caches
- Gradle caches
- CocoaPods cache
- Expo CLI cache
- Watchman, TypeScript, Swift PM, and ccache

### Project-Level

- `node_modules` — Node.js dependencies
- `ios/Pods` — CocoaPods dependencies
- `ios/build`, `android/build`, `android/app/build` — Native build outputs
- `.expo`, `.next`, `.nuxt`, `.turbo` — Framework caches
- `dist` — Build output

## Requirements

- macOS
- Python 3.7+
- No external packages
