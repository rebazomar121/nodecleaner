<img width="1080" height="1080" alt="nodecleaner-hero (1)" src="https://github.com/user-attachments/assets/d7bc623e-9b7b-4a3a-a39e-3ffe3e4ffc3a" />


# NodeCleaner

A Python CLI tool that cleans junk files from Node.js, React Native, and Expo development on macOS.

## Features

- **System cache cleaning** — Xcode, npm, Yarn, pnpm, Bun, Gradle, CocoaPods, Metro, and more
- **Project scanning** — Finds `node_modules`, build outputs, and framework caches across your projects
- **Interactive selector** — Arrow keys to navigate, space to toggle, 'a' to select all
- **Safe deletion** — Type "yes" to confirm, with full summary of what will be removed
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

- macOS (Linux works for the non-Apple paths)
- Python 3.8+
- No external packages

## Development

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e . pytest
pytest
```
