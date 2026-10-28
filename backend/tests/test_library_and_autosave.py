"""Library folder lifecycle, the location index, and per-change autosave."""

import json
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import persistence, resource_service
from app.services.store import KairosStore, store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    store.reset()
    persistence.set_autosave(False)
    yield
    persistence.set_autosave(False)
    store.reset()


def write(path, text="notes about the project report and citations"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def locations(s=store):
    return {r["location"] for r in s.all_resources()}


# ---------------------------------------------------------------------- #
# location index
# ---------------------------------------------------------------------- #
def test_location_index_tracks_add_replace_and_remove(tmp_path):
    s = KairosStore()
    f = write(str(tmp_path / "a" / "Report_Draft.md"))
    resource_service.index_folder(s, str(tmp_path / "a"))
    first = s.find_resource_by_location(f)
    assert first is not None and first["title"] == "Report_Draft.md"
    assert s.location_index.size == s.resource_index.size == 1

    # A changed file is replaced under a new id; the index follows it.
    write(f, "a much longer replacement body about methodology and results")
    resource_service.index_folder(s, str(tmp_path / "a"))
    second = s.find_resource_by_location(f)
    assert second["id"] != first["id"]
    assert s.get_resource(first["id"]) is None
    assert s.location_index.size == 1

    s.remove_resource(second["id"])
    assert s.find_resource_by_location(f) is None
    assert s.location_index.size == 0


# ---------------------------------------------------------------------- #
# pruning on re-index
# ---------------------------------------------------------------------- #
def test_reindex_removes_files_deleted_from_disk(tmp_path):
    keep = write(str(tmp_path / "lib" / "Keep_Notes.md"))
    gone = write(str(tmp_path / "lib" / "sub" / "Zebra_Unique_Notes.md"), "zebra zebra zebra")
    first = resource_service.index_folder(store, str(tmp_path / "lib"))
    assert first["indexed"] == 2 and first["removed"] == 0
    assert store.keyword_trie.search("zebra")

    os.remove(gone)
    second = resource_service.index_folder(store, str(tmp_path / "lib"))
    assert second["removed"] == 1
    assert locations() == {keep}
    # the trie no longer points at the deleted file
    assert resource_service.search_resources(store, "zebra")["results"] == []


def test_switching_to_non_recursive_prunes_nested_files(tmp_path):
    top = write(str(tmp_path / "lib" / "Top_Level.md"))
    write(str(tmp_path / "lib" / "nested" / "Nested_File.md"))
    resource_service.index_folder(store, str(tmp_path / "lib"))
    assert len(locations()) == 2

    result = resource_service.index_folder(store, str(tmp_path / "lib"), recursive=False)
    assert result["removed"] == 1
    assert locations() == {top}


def test_non_recursive_scan_does_not_index_subfolders_as_files(tmp_path):
    write(str(tmp_path / "lib" / "Only_File.md"))
    os.makedirs(tmp_path / "lib" / "a_subfolder")
    result = resource_service.index_folder(store, str(tmp_path / "lib"), recursive=False)
    assert result["indexed"] == 1
    assert [r["title"] for r in store.all_resources()] == ["Only_File.md"]


def test_child_folder_entries_survive_parent_rescan_exclusion(tmp_path):
    parent = tmp_path / "lib"
    nested = write(str(parent / "child" / "Child_Notes.md"))
    resource_service.index_folder(store, str(parent / "child"))
    # The parent is added non-recursively: its scan does not reach child/,
    # but child/ is still registered, so the entry must stay.
    resource_service.index_folder(store, str(parent), recursive=False)
    assert nested in locations()


# ---------------------------------------------------------------------- #
# folder registry through the API
# ---------------------------------------------------------------------- #
def test_index_registers_folder_and_lists_counts(tmp_path):
    write(str(tmp_path / "lib" / "One.md"))
    write(str(tmp_path / "lib" / "deep" / "Two.md"))
    response = client.post("/api/resources/index", json={"path": str(tmp_path / "lib"), "tags": ["Course"]})
    assert response.status_code == 200
    assert response.json()["removed"] == 0

    listing = client.get("/api/resources/folders").json()
    assert listing["unmanaged_count"] == 0
    (folder,) = listing["folders"]
    assert folder["path"] == os.path.realpath(str(tmp_path / "lib"))
    assert folder["resource_count"] == 2
    assert folder["tags"] == ["course"]
    assert folder["exists"] is True
    assert folder["last_result"]["indexed"] == 2


def test_rescan_one_folder_reuses_saved_options(tmp_path):
    lib = tmp_path / "lib"
    write(str(lib / "Top.md"))
    write(str(lib / "nested" / "Nested.md"))
    client.post("/api/resources/index", json={"path": str(lib), "tags": ["kept"], "recursive": False})
    assert len(locations()) == 1

    added = write(str(lib / "Second_Top.md"))
    response = client.post("/api/resources/folders/rescan", json={"path": str(lib)})
    assert response.status_code == 200
    body = response.json()
    assert body["indexed"] == 1
    assert added in locations()
    # still non-recursive, still tagged
    assert all("nested" not in loc for loc in locations())
    assert all(r["tags"] == ["kept"] for r in store.all_resources())


def test_rescan_all_reports_a_missing_folder_without_stopping(tmp_path):
    write(str(tmp_path / "a" / "A.md"))
    write(str(tmp_path / "b" / "B.md"))
    client.post("/api/resources/index", json={"path": str(tmp_path / "a")})
    client.post("/api/resources/index", json={"path": str(tmp_path / "b")})
    os.remove(tmp_path / "b" / "B.md")
    os.rmdir(tmp_path / "b")
    write(str(tmp_path / "a" / "A2.md"))

    body = client.post("/api/resources/folders/rescan", json={}).json()
    outcomes = {os.path.basename(r["path"]): r["ok"] for r in body["results"]}
    assert outcomes == {"a": True, "b": False}
    assert body["indexed"] == 1


def test_rescan_errors(tmp_path):
    assert client.post("/api/resources/folders/rescan", json={"path": str(tmp_path)}).status_code == 404
    write(str(tmp_path / "gone" / "G.md"))
    client.post("/api/resources/index", json={"path": str(tmp_path / "gone")})
    os.remove(tmp_path / "gone" / "G.md")
    os.rmdir(tmp_path / "gone")
    response = client.post("/api/resources/folders/rescan", json={"path": str(tmp_path / "gone")})
    assert response.status_code == 400
    assert "Remove it from the library" in response.json()["detail"]


def test_remove_folder_forgets_entries_but_keeps_files(tmp_path):
    f = write(str(tmp_path / "lib" / "Paper.md"), "unique quokka content")
    client.post("/api/resources/index", json={"path": str(tmp_path / "lib")})
    response = client.delete("/api/resources/folders", params={"path": str(tmp_path / "lib")})
    assert response.status_code == 200
    assert response.json()["removed"] == 1
    assert store.all_resources() == []
    assert store.location_index.size == 0
    assert client.get("/api/resources/folders").json()["folders"] == []
    assert resource_service.search_resources(store, "quokka")["results"] == []
    assert os.path.exists(f)  # the file on disk is untouched
    assert client.delete("/api/resources/folders", params={"path": str(tmp_path / "lib")}).status_code == 404


def test_removing_child_folder_keeps_entries_the_parent_covers(tmp_path):
    shared = write(str(tmp_path / "lib" / "child" / "Shared.md"))
    client.post("/api/resources/index", json={"path": str(tmp_path / "lib" / "child")})
    client.post("/api/resources/index", json={"path": str(tmp_path / "lib")})
    removed = client.delete("/api/resources/folders", params={"path": str(tmp_path / "lib" / "child")}).json()
    assert removed["removed"] == 0
    assert shared in locations()


def test_unmanaged_count_for_entries_indexed_before_folder_tracking(tmp_path):
    f = write(str(tmp_path / "old" / "Legacy.md"))
    resource_service.index_folder(store, str(tmp_path / "old"))
    store.remove_folder_record(str(tmp_path / "old"))  # as if restored from a v2 snapshot
    assert client.get("/api/resources/folders").json()["unmanaged_count"] == 1
    # indexing the folder again brings it back under management
    client.post("/api/resources/index", json={"path": str(tmp_path / "old")})
    listing = client.get("/api/resources/folders").json()
    assert listing["unmanaged_count"] == 0
    assert f in locations()


def test_folders_route_is_not_shadowed_by_resource_lookup():
    assert client.get("/api/resources/folders").status_code == 200
    assert client.get("/api/resources/R9999").status_code == 404


# ---------------------------------------------------------------------- #
# snapshot format
# ---------------------------------------------------------------------- #
def test_folders_round_trip_through_a_snapshot(tmp_path):
    write(str(tmp_path / "lib" / "Doc.md"))
    s = KairosStore()
    resource_service.index_folder(s, str(tmp_path / "lib"), tags=["x"], recursive=False)
    path = str(tmp_path / "snap.json")
    saved = persistence.save(s, path)
    assert saved["folders"] == 1

    fresh = KairosStore()
    persistence.restore(fresh, path)
    (folder,) = fresh.folders()
    assert folder["recursive"] is False and folder["tags"] == ["x"]
    assert fresh.find_resource_by_location(str(tmp_path / "lib" / "Doc.md")) is not None


def test_version_2_snapshot_without_folders_still_restores(tmp_path):
    path = tmp_path / "v2.json"
    path.write_text(json.dumps({
        "version": 2, "saved_at": "2026-10-01T00:00:00+00:00",
        "tasks": [], "mastery": [], "focus_sessions": [], "settings": {},
        "resources": [{
            "id": "R0007", "title": "Old.md", "source": "local", "kind": "notes",
            "location": "/nowhere/Old.md", "tags": [], "keywords": ["old"],
            "content_keywords": [], "snippet": "",
        }],
    }), encoding="utf-8")
    fresh = KairosStore()
    result = persistence.restore(fresh, str(path))
    assert result["loaded"] is True and result["folders"] == 0
    assert fresh.find_resource_by_location("/nowhere/Old.md")["id"] == "R0007"
    assert fresh.next_resource_id() == "R0008"


def test_malformed_folder_record_is_rejected_without_touching_the_store(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 3, "folders": [{"tags": []}]}), encoding="utf-8")
    live = KairosStore()
    live.settings["available_hours_per_day"] = 5
    with pytest.raises(ValueError):
        persistence.restore(live, str(path))
    assert live.settings["available_hours_per_day"] == 5


# ---------------------------------------------------------------------- #
# autosave
# ---------------------------------------------------------------------- #
def _task_payload(title="Autosaved task"):
    return {
        "title": title,
        "deadline": (date.today() + timedelta(days=4)).isoformat(),
        "priority": "HIGH",
        "estimated_hours": 3,
    }


def _saved_titles(path):
    with open(path, encoding="utf-8") as fh:
        return [t["title"] for t in json.load(fh)["tasks"]]


def test_changes_are_saved_while_the_server_runs(tmp_path, monkeypatch):
    snap = str(tmp_path / "live.json")
    monkeypatch.setattr(persistence, "DEFAULT_SNAPSHOT_PATH", snap)
    monkeypatch.delenv("KAIROS_AUTOSAVE", raising=False)
    with TestClient(app) as live:
        created = live.post("/api/tasks", json=_task_payload()).json()["task"]
        # saved immediately, before any shutdown hook has run
        assert _saved_titles(snap) == ["Autosaved task"]

        live.patch(f"/api/tasks/{created['id']}", json={"progress": 40})
        with open(snap, encoding="utf-8") as fh:
            assert json.load(fh)["tasks"][0]["progress"] == 40

        live.patch("/api/settings", json={"available_hours_per_day": 1.5})
        with open(snap, encoding="utf-8") as fh:
            assert json.load(fh)["settings"]["available_hours_per_day"] == 1.5

        status = live.get("/api/snapshot/status").json()
        assert status["autosave"]["enabled"] is True
        assert status["autosave"]["last_error"] is None
        assert status["autosave"]["saves"] >= 3
    assert not os.path.exists(snap + ".tmp")


def test_read_only_posts_and_failed_requests_do_not_save(tmp_path, monkeypatch):
    snap = str(tmp_path / "live.json")
    monkeypatch.setattr(persistence, "DEFAULT_SNAPSHOT_PATH", snap)
    monkeypatch.delenv("KAIROS_AUTOSAVE", raising=False)
    with TestClient(app) as live:
        before = persistence.autosave_status()["saves"]
        assert live.post("/api/plan", json={"capacity_hours": 10, "daily_hours": 2}).status_code == 200
        assert live.patch("/api/tasks/T9999", json={"progress": 10}).status_code == 404
        assert live.post("/api/tasks", json={"title": " "}).status_code == 422
        assert persistence.autosave_status()["saves"] == before
        assert not os.path.exists(snap)


def test_autosave_can_be_turned_off(tmp_path, monkeypatch):
    snap = str(tmp_path / "off.json")
    monkeypatch.setattr(persistence, "DEFAULT_SNAPSHOT_PATH", snap)
    monkeypatch.setenv("KAIROS_AUTOSAVE", "0")
    with TestClient(app) as live:
        live.post("/api/tasks", json=_task_payload())
        assert not os.path.exists(snap)
        assert live.get("/api/snapshot/status").json()["autosave"]["enabled"] is False
    # the shutdown save still runs
    assert _saved_titles(snap) == ["Autosaved task"]


def test_a_failed_autosave_is_reported_but_does_not_fail_the_request(tmp_path, monkeypatch):
    blocked = tmp_path / "is_a_folder"
    blocked.mkdir()
    monkeypatch.setattr(persistence, "DEFAULT_SNAPSHOT_PATH", str(blocked))
    monkeypatch.delenv("KAIROS_AUTOSAVE", raising=False)
    with TestClient(app) as live:
        assert live.post("/api/tasks", json=_task_payload()).status_code == 201
        state = live.get("/api/snapshot/status").json()["autosave"]
        assert state["last_error"]


def test_restart_restores_what_autosave_wrote(tmp_path, monkeypatch):
    snap = str(tmp_path / "restart.json")
    monkeypatch.setattr(persistence, "DEFAULT_SNAPSHOT_PATH", snap)
    monkeypatch.delenv("KAIROS_AUTOSAVE", raising=False)
    with TestClient(app) as live:
        live.post("/api/tasks", json=_task_payload("Survives a crash"))
        # Simulate an abrupt stop: copy the file as it is now, before the
        # graceful shutdown hook gets a chance to write again.
        with open(snap, encoding="utf-8") as fh:
            crash_copy = fh.read()
    with open(snap, "w", encoding="utf-8") as fh:
        fh.write(crash_copy)
    store.reset()
    with TestClient(app) as restarted:
        titles = [t["title"] for t in restarted.get("/api/tasks").json()["tasks"]]
    assert titles == ["Survives a crash"]
