"""Smoke tests for the safe, non-destructive parts of NodeCleaner."""

import json
import os

from nodecleaner import core


def test_format_size_units():
    assert core.format_size(0) == "0 B"
    assert core.format_size(512) == "512 B"
    assert core.format_size(1024) == "1.0 KB"
    assert core.format_size(1024 * 1024) == "1.0 MB"
    assert core.format_size(1024 ** 3) == "1.0 GB"


def test_format_size_negative_is_zero():
    assert core.format_size(-5) == "0 B"


def test_get_dir_size_counts_files(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 100)
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_bytes(b"y" * 50)
    assert core._get_dir_size(str(tmp_path)) == 150


def test_get_dir_size_missing_path_is_zero():
    assert core._get_dir_size("/path/that/does/not/exist") == 0


def test_scan_projects_finds_node_modules(tmp_path):
    project = tmp_path / "myapp"
    nm = project / "node_modules"
    nm.mkdir(parents=True)
    (nm / "pkg.js").write_bytes(b"z" * 200)

    targets = core.scan_projects(str(tmp_path))
    paths = [os.path.realpath(t.path) for t in targets]
    assert os.path.realpath(str(nm)) in paths


def test_scan_projects_empty_dir_returns_nothing(tmp_path):
    assert core.scan_projects(str(tmp_path)) == []


def test_scan_projects_missing_dir_returns_nothing():
    assert core.scan_projects("/path/that/does/not/exist") == []


# ── Docker ──────────────────────────────────────────────────────────────────

def test_parse_docker_size_uses_decimal_units():
    assert core._parse_docker_size("0B") == 0
    assert core._parse_docker_size("12.5kB") == 12_500
    assert core._parse_docker_size("512MB") == 512_000_000
    assert core._parse_docker_size("1.5GB") == 1_500_000_000
    assert core._parse_docker_size("N/A") == 0
    assert core._parse_docker_size(None) == 0


def test_parse_docker_time_handles_docker_formats():
    # Image `Created`: nanosecond precision with a Z suffix.
    assert core._parse_docker_time("2024-01-01T00:00:00.123456789Z") == 1704067200.123456
    # Volume `CreatedAt`: no fraction, explicit offset.
    assert core._parse_docker_time("2024-01-01T03:00:00+03:00") == 1704067200.0
    # Go's zero time means "never".
    assert core._parse_docker_time("0001-01-01T00:00:00Z") == 0.0
    assert core._parse_docker_time(None) == 0.0
    assert core._parse_docker_time("not a date") == 0.0


def test_relative_age():
    now = 1_000_000_000
    assert core._relative_age(0) == "unknown age"
    assert core._relative_age(now - 5, now) == "just now"
    assert core._relative_age(now - 3600, now) == "1 hour ago"
    assert core._relative_age(now - 3 * 86400, now) == "3 days ago"
    assert core._relative_age(now - 60 * 86400, now) == "2 months ago"


def test_shorten_middle_keeps_both_ends():
    assert core._shorten_middle("short", 10) == "short"
    out = core._shorten_middle("registry.example.com/team/app:latest", 20)
    assert len(out) == 20
    assert out.startswith("registry.") and out.endswith(":latest")


def _fake_docker_run_factory(system_df_output):
    """Build a fake `_docker_run` serving a small Docker world.

    - image aaa is used by a stopped container, image bbb is free (2 tags),
      image ccc is dangling
    - volume used_vol is mounted by that container, old_vol / new_vol are free
    """
    images = [
        {"Id": "sha256:aaa", "RepoTags": ["inuse:1"], "Size": 10,
         "Created": "2024-01-01T00:00:00Z", "Metadata": {"LastTagTime": "0001-01-01T00:00:00Z"}},
        {"Id": "sha256:bbb", "RepoTags": ["myapp:latest", "myapp:1.0"], "Size": 300,
         "Created": "2023-06-01T00:00:00Z", "Metadata": {"LastTagTime": "2024-03-01T00:00:00Z"}},
        {"Id": "sha256:ccc", "RepoTags": [], "Size": 20,
         "Created": "2022-01-01T00:00:00Z", "Metadata": {}},
    ]
    volumes = [
        {"Name": "used_vol", "CreatedAt": "2024-01-01T00:00:00Z"},
        {"Name": "old_vol", "CreatedAt": "2021-01-01T00:00:00Z"},
        {"Name": "new_vol", "CreatedAt": "2024-06-01T00:00:00Z"},
    ]
    container = {"Image": "sha256:aaa",
                 "Mounts": [{"Type": "volume", "Name": "used_vol"}, {"Type": "bind"}]}

    def fake(args, timeout=0):
        head = args[:2]
        if head == ["container", "ls"]:
            return "c1\n"
        if head == ["container", "inspect"]:
            return json.dumps(container) + "\n"
        if head == ["image", "ls"]:
            return "sha256:aaa\nsha256:bbb\nsha256:bbb\nsha256:ccc\n"
        if head == ["image", "inspect"]:
            return "".join(json.dumps(i) + "\n" for i in images)
        if head == ["volume", "ls"]:
            return "used_vol\nold_vol\nnew_vol\n"
        if head == ["volume", "inspect"]:
            return "".join(json.dumps(v) + "\n" for v in volumes)
        if head == ["system", "df"]:
            return system_df_output
        raise AssertionError(f"unexpected docker call: {args}")

    return fake


def test_scan_docker_skips_in_use_and_sorts_oldest_first(monkeypatch):
    df = json.dumps({"Volumes": [{"Name": "old_vol", "Size": "1.5GB"},
                                  {"Name": "new_vol", "Size": "0B"}]})
    monkeypatch.setattr(core, "_docker_run", _fake_docker_run_factory(df))

    targets, skipped = core.scan_docker()

    assert skipped == 2  # image aaa + used_vol
    assert [t.path for t in targets] == ["old_vol", "sha256:ccc", "sha256:bbb", "new_vol"]

    by_path = {t.path: t for t in targets}
    # Multi-tag image is removed by untagging every tag, never by ID.
    assert by_path["sha256:bbb"].command == ["docker", "image", "rm", "myapp:latest", "myapp:1.0"]
    assert "myapp:latest +1" in by_path["sha256:bbb"].description
    # Dangling image falls back to its ID.
    assert by_path["sha256:ccc"].command == ["docker", "image", "rm", "sha256:ccc"]
    assert "<dangling> ccc" in by_path["sha256:ccc"].description
    assert by_path["old_vol"].command == ["docker", "volume", "rm", "old_vol"]
    assert by_path["old_vol"].size == 1_500_000_000
    assert by_path["old_vol"].category is core.Category.DOCKER_VOLUME
    assert by_path["sha256:bbb"].category is core.Category.DOCKER_IMAGE
    assert all(t.command for t in targets)


def test_scan_docker_without_df_support_still_lists_volumes(monkeypatch):
    monkeypatch.setattr(core, "_docker_run", _fake_docker_run_factory(None))
    targets, _ = core.scan_docker()
    vols = [t for t in targets if t.category is core.Category.DOCKER_VOLUME]
    assert {t.path for t in vols} == {"old_vol", "new_vol"}
    assert all(t.size == 0 for t in vols)


def test_scan_docker_no_daemon_returns_nothing(monkeypatch):
    monkeypatch.setattr(core, "_docker_run", lambda args, timeout=0: None)
    assert core.scan_docker() == ([], 0)


def test_docker_available_without_cli(monkeypatch):
    monkeypatch.setattr(core.shutil, "which", lambda name: None)
    ok, message = core.docker_available()
    assert ok is False
    assert "not found" in message


# ── Interactive selector sorting ─────────────────────────────────────────────

def _target(path, size, timestamp=0.0):
    return core.CleanupTarget(path=path, description=path, category=core.Category.DIST,
                              size=size, timestamp=timestamp)


def test_selector_cycles_size_sort_and_keeps_cursor():
    targets = [_target("big", 300), _target("mid", 200), _target("small", 100)]
    sel = core.InteractiveSelector(targets)
    assert sel._sort_modes[0][0] == "largest first"

    sel.cursor = 2  # on "small"
    sel._cycle_sort()
    assert [t.path for t in sel.targets] == ["small", "mid", "big"]
    assert sel.targets[sel.cursor].path == "small"

    sel._cycle_sort()  # wraps back to largest first
    assert [t.path for t in sel.targets] == ["big", "mid", "small"]


def test_selector_docker_list_toggles_between_age_and_size():
    targets = [_target("old-small", 10, timestamp=100), _target("new-big", 500, timestamp=900)]
    sel = core.InteractiveSelector(targets)
    assert sel._sort_modes[0][0] == "oldest first"

    sel._cycle_sort()
    assert [t.path for t in sel.targets] == ["new-big", "old-small"]
    sel._cycle_sort()
    assert [t.path for t in sel.targets] == ["old-small", "new-big"]
