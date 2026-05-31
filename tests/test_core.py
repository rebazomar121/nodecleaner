"""Smoke tests for the safe, non-destructive parts of NodeCleaner."""

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
