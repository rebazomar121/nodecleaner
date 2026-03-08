#!/usr/bin/env python3
"""NodeCleaner - Clean junk files from Node.js/React Native/Expo development on macOS."""

import enum
import glob
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

VERSION = "1.0.0"


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


@dataclass
class CleanupTarget:
    path: str
    description: str
    category: Category
    size: int = 0
    selected: bool = False


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
]

TMPDIR_PATTERNS = [
    ("react-native-packager-cache-*", "RN packager cache", Category.REACT_NATIVE),
    ("metro-bundler-cache-*", "Metro bundler cache", Category.METRO),
    ("metro-cache", "Metro cache", Category.METRO),
    ("haste-map-*", "Haste map cache", Category.REACT_NATIVE),
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
]

# Directories to skip when walking the project tree
PRUNE_DIRS = {"node_modules", ".git", ".hg", ".svn", "__pycache__", ".Trash"}


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


def scan_system_caches() -> List[CleanupTarget]:
    """Scan fixed system cache paths."""
    targets = []
    seen = set()

    # Fixed paths
    for path, desc, cat in SYSTEM_TARGETS:
        real = os.path.realpath(path)
        if real in seen:
            continue
        if os.path.isdir(path):
            seen.add(real)
            size = _get_dir_size(path)
            if size > 0:
                targets.append(CleanupTarget(path=path, description=desc, category=cat, size=size))

    # Tmpdir glob patterns
    for pattern, desc, cat in TMPDIR_PATTERNS:
        full_pattern = os.path.join(TMPDIR, pattern)
        for match in glob.glob(full_pattern):
            real = os.path.realpath(match)
            if real in seen:
                continue
            if os.path.isdir(match):
                seen.add(real)
                size = _get_dir_size(match)
                if size > 0:
                    targets.append(CleanupTarget(path=match, description=desc, category=cat, size=size))

    targets.sort(key=lambda t: t.size, reverse=True)
    return targets


def scan_projects(base_dir: str) -> List[CleanupTarget]:
    """Scan a projects directory for cleanable targets using os.walk with pruning."""
    targets = []
    seen = set()
    base_dir = os.path.expanduser(base_dir)

    if not os.path.isdir(base_dir):
        return targets

    for dirpath, dirnames, filenames in os.walk(base_dir, followlinks=False):
        # Prune directories we don't want to walk into
        dirnames[:] = [
            d for d in dirnames
            if d not in PRUNE_DIRS and not d.startswith(".")
            or d in (".expo", ".next", ".nuxt", ".turbo")
        ]

        # Check each possible target
        for dirname, desc, cat in PROJECT_SCAN_DIRS:
            candidate = os.path.join(dirpath, dirname)
            if os.path.isdir(candidate):
                real = os.path.realpath(candidate)
                if real in seen:
                    continue
                seen.add(real)
                size = _get_dir_size(candidate)
                if size > 0:
                    targets.append(CleanupTarget(
                        path=candidate, description=desc, category=cat, size=size
                    ))

        # Further prune: if we found node_modules here, don't go into it
        if "node_modules" in dirnames:
            dirnames.remove("node_modules")

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

            # Shorten path for display
            display_path = t.path.replace(HOME, "~")
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
        label = target.path.replace(HOME, "~")
        if len(label) > 40:
            label = "..." + label[-37:]
        sys.stdout.write(progress_bar(i, total, label=label))
        sys.stdout.flush()

        try:
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
    print(f"  {Colors.GREEN}{Colors.BOLD}Cleanup Complete!{Colors.RESET}")
    print(f"  {Colors.BOLD}{'═' * 44}{Colors.RESET}")
    print(f"  {Colors.GREEN}✓ Deleted:{Colors.RESET}  {success} items")
    if failed > 0:
        print(f"  {Colors.RED}✗ Failed:{Colors.RESET}   {failed} items")
    print(f"  {Colors.CYAN}♻ Freed:{Colors.RESET}    {Colors.BOLD}{format_size(freed)}{Colors.RESET}")
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
                self._show_about()
            elif choice == "5":
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
        print(f"  {Colors.CYAN}[4]{Colors.RESET} About")
        print(f"  {Colors.CYAN}[5]{Colors.RESET} Exit")
        print()

        try:
            choice = input(f"  {Colors.BOLD}Choose an option [1-5]:{Colors.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "5"
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
        print(f"  {Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} WARNING {Colors.RESET}")
        print(f"  You are about to delete {Colors.BOLD}{len(selected)}{Colors.RESET} items "
              f"({Colors.YELLOW}{format_size(total_size)}{Colors.RESET})")
        print()

        # Show what will be deleted
        for t in selected[:10]:
            display_path = t.path.replace(HOME, "~")
            print(f"    {Colors.RED}•{Colors.RESET} {display_path}")
        if len(selected) > 10:
            print(f"    {Colors.DIM}... and {len(selected) - 10} more{Colors.RESET}")

        print()
        print(f"  {Colors.RED}{Colors.BOLD}This action cannot be undone!{Colors.RESET}")

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
        print()
        print(f"  {Colors.DIM}Pure Python — no external dependencies{Colors.RESET}")
        print()

    def _exit(self):
        """Exit the application."""
        print(f"  {Colors.GREEN}Goodbye!{Colors.RESET}\n")
        sys.exit(0)


def main():
    if sys.platform != "darwin":
        print("Warning: NodeCleaner is designed for macOS. Some paths may not exist on your system.")

    app = NodeCleaner()
    app.run()


if __name__ == "__main__":
    main()
