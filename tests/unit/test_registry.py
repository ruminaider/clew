"""Tests for the central project registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import clew.registry
from clew.registry import (
    _load_registry,
    _save_registry,
    find_project,
    list_projects,
    register_project,
    unregister_project,
)


@pytest.fixture(autouse=True)
def _isolated_registry(tmp_path, monkeypatch):
    """Redirect registry to a temp directory for all tests."""
    registry_dir = tmp_path / ".clew"
    registry_dir.mkdir()
    monkeypatch.setattr(
        "clew.registry._registry_path",
        lambda: registry_dir / "projects.json",
    )


class TestRegistryPath:
    def test_returns_path_under_home(self, monkeypatch):
        """Default registry path is ~/.clew/projects.json."""
        monkeypatch.undo()
        path = clew.registry._registry_path()
        assert path == Path.home() / ".clew" / "projects.json"


class TestLoadSave:
    def test_load_missing_file_returns_empty(self):
        data = _load_registry()
        assert data == {"projects": {}}

    def test_save_and_load_roundtrip(self):
        data = {"projects": {"test": {"project_root": "/tmp/test"}}}
        _save_registry(data)
        loaded = _load_registry()
        assert loaded == data

    def test_load_corrupt_json_returns_empty(self):
        path = clew.registry._registry_path()
        path.write_text("{bad json")
        data = _load_registry()
        assert data == {"projects": {}}

    def test_load_missing_projects_key(self):
        path = clew.registry._registry_path()
        path.write_text(json.dumps({"version": 1}))
        data = _load_registry()
        assert "projects" in data

    def test_save_creates_parent_directory(self, tmp_path, monkeypatch):
        """Save creates parent dirs if they don't exist."""
        new_dir = tmp_path / "fresh" / ".clew"
        monkeypatch.setattr(
            "clew.registry._registry_path",
            lambda: new_dir / "projects.json",
        )
        data = {"projects": {"x": {"project_root": "/tmp/x"}}}
        _save_registry(data)
        assert (new_dir / "projects.json").exists()


class TestRegisterProject:
    def test_register_new_project(self, tmp_path):
        root = tmp_path / "myproject"
        root.mkdir()
        cache = root / ".clew"
        cache.mkdir()

        register_project("myproject", root, cache, "myproject-code")

        data = _load_registry()
        assert "myproject" in data["projects"]
        entry = data["projects"]["myproject"]
        assert entry["project_root"] == str(root.resolve())
        assert entry["cache_dir"] == str(cache.resolve())
        assert entry["collection_name"] == "myproject-code"
        assert "last_indexed" in entry

    def test_register_updates_existing(self, tmp_path):
        root = tmp_path / "proj"
        root.mkdir()
        cache = root / ".clew"
        cache.mkdir()

        register_project("proj", root, cache, "old-collection")
        register_project("proj", root, cache, "new-collection")

        data = _load_registry()
        assert data["projects"]["proj"]["collection_name"] == "new-collection"

    def test_register_multiple_projects(self, tmp_path):
        for name in ["alpha", "beta", "gamma"]:
            d = tmp_path / name
            d.mkdir()
            register_project(name, d, d / ".clew", f"{name}-code")

        data = _load_registry()
        assert len(data["projects"]) == 3


class TestListProjects:
    def test_empty_registry(self):
        assert list_projects() == []

    def test_returns_sorted_by_name(self, tmp_path):
        for name in ["zeta", "alpha", "mid"]:
            d = tmp_path / name
            d.mkdir()
            register_project(name, d, d / ".clew", f"{name}-code")

        projects = list_projects()
        names = [p["name"] for p in projects]
        assert names == ["alpha", "mid", "zeta"]

    def test_entries_have_all_fields(self, tmp_path):
        d = tmp_path / "proj"
        d.mkdir()
        register_project("proj", d, d / ".clew", "proj-code")

        projects = list_projects()
        assert len(projects) == 1
        p = projects[0]
        assert set(p.keys()) == {
            "name",
            "project_root",
            "cache_dir",
            "collection_name",
            "last_indexed",
        }


class TestFindProject:
    @pytest.fixture()
    def _three_projects(self, tmp_path):
        """Register three projects for find tests."""
        for name, subdir in [("evvy", "Work/evvy"), ("clew", "Repos/clew"), ("api", "Work/api")]:
            d = tmp_path / subdir
            d.mkdir(parents=True)
            register_project(name, d, d / ".clew", f"{name}-code")

    def test_find_by_exact_name(self, _three_projects):
        result = find_project("evvy")
        assert result is not None
        assert result["name"] == "evvy"
        assert result["collection_name"] == "evvy-code"

    def test_find_by_exact_path(self, _three_projects, tmp_path):
        path = str(tmp_path / "Work" / "evvy")
        result = find_project(path)
        assert result is not None
        assert result["name"] == "evvy"

    def test_find_by_basename(self, _three_projects):
        result = find_project("clew")
        assert result is not None
        assert result["name"] == "clew"

    def test_find_returns_none_for_unknown(self, _three_projects):
        assert find_project("nonexistent") is None

    def test_find_prefers_exact_name_over_basename(self, tmp_path):
        """When name matches directly, don't fall through to basename matching."""
        d1 = tmp_path / "proj-a"
        d1.mkdir()
        register_project("myapp", d1, d1 / ".clew", "myapp-code")

        d2 = tmp_path / "myapp"
        d2.mkdir()
        register_project("other", d2, d2 / ".clew", "other-code")

        # "myapp" should match the name "myapp", not the basename of d2
        result = find_project("myapp")
        assert result is not None
        assert result["name"] == "myapp"


class TestUnregisterProject:
    def test_unregister_existing(self, tmp_path):
        d = tmp_path / "proj"
        d.mkdir()
        register_project("proj", d, d / ".clew", "proj-code")

        assert unregister_project("proj") is True
        assert list_projects() == []

    def test_unregister_nonexistent(self):
        assert unregister_project("nope") is False

    def test_unregister_preserves_others(self, tmp_path):
        for name in ["a", "b", "c"]:
            d = tmp_path / name
            d.mkdir()
            register_project(name, d, d / ".clew", f"{name}-code")

        unregister_project("b")
        names = [p["name"] for p in list_projects()]
        assert names == ["a", "c"]
