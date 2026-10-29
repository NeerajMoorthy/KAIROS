"""User accounts: sign-up, log-in, private workspaces, and required login."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.services.accounts import AccountService
from app.services.storage import FileStorage
from app.services.store import store as local_store

client = TestClient(app)
DEADLINE = (date.today() + timedelta(days=5)).isoformat()


@pytest.fixture(autouse=True)
def fresh_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_accounts", AccountService(FileStorage(str(tmp_path))))
    monkeypatch.setattr(main, "REQUIRE_LOGIN", False)
    local_store.reset()
    yield tmp_path
    local_store.reset()


def sign_up(username, password="correct horse"):
    response = client.post("/api/auth/signup", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def add_task(headers, title):
    response = client.post(
        "/api/tasks",
        headers=headers,
        json={"title": title, "deadline": DEADLINE, "estimated_hours": 2},
    )
    assert response.status_code == 201, response.text


def titles(headers=None):
    return [t["title"] for t in client.get("/api/tasks", headers=headers or {}).json()["tasks"]]


def test_each_user_sees_only_their_own_tasks():
    alice, bob = sign_up("alice"), sign_up("bob")
    add_task(alice, "Alice essay")
    add_task(bob, "Bob lab")
    assert titles(alice) == ["Alice essay"]
    assert titles(bob) == ["Bob lab"]
    assert titles() == []  # the shared local workspace is untouched


def test_log_in_returns_to_the_same_workspace():
    add_task(sign_up("alice"), "Alice essay")
    response = client.post("/api/auth/login", json={"username": "ALICE ", "password": "correct horse"})
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    assert titles(headers) == ["Alice essay"]
    assert client.get("/api/auth/me", headers=headers).json()["username"] == "alice"


def test_wrong_password_and_unknown_user_give_the_same_error():
    sign_up("alice")
    wrong = client.post("/api/auth/login", json={"username": "alice", "password": "nope nope"})
    unknown = client.post("/api/auth/login", json={"username": "nobody", "password": "nope nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_sign_up_validation():
    sign_up("alice")
    assert client.post("/api/auth/signup", json={"username": "alice", "password": "another one"}).status_code == 400
    assert client.post("/api/auth/signup", json={"username": "a", "password": "long enough"}).status_code == 400
    assert client.post("/api/auth/signup", json={"username": "carol", "password": "short"}).status_code == 400


def test_passwords_are_not_stored_in_plain_text(fresh_accounts):
    sign_up("alice", "my secret password")
    saved = (fresh_accounts / "accounts.json").read_text()
    assert "my secret password" not in saved


def test_log_out_ends_the_session():
    alice = sign_up("alice")
    assert client.post("/api/auth/logout", headers=alice).status_code == 200
    response = client.get("/api/tasks", headers=alice)
    assert response.status_code == 401
    assert "log in again" in response.json()["detail"]


def test_required_login_blocks_data_but_not_health_or_auth(monkeypatch):
    monkeypatch.setattr(main, "REQUIRE_LOGIN", True)
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/demo/seed").status_code == 401
    assert client.get("/api/health").json()["login_required"] is True
    alice = sign_up("alice")
    assert client.get("/api/tasks", headers=alice).status_code == 200


def test_accounts_and_workspaces_survive_a_restart(fresh_accounts, monkeypatch):
    alice = sign_up("alice")
    add_task(alice, "Alice essay")
    # a new service reads everything back from storage, as after a restart
    monkeypatch.setattr(main, "_accounts", AccountService(FileStorage(str(fresh_accounts))))
    assert titles(alice) == ["Alice essay"]


def test_example_data_loads_into_the_users_workspace():
    alice = sign_up("alice")
    assert client.post("/api/demo/seed", headers=alice).status_code == 200
    assert len(titles(alice)) > 0
    assert titles() == []
    status = client.get("/api/snapshot/status", headers=alice).json()
    assert status["account"] == "alice" and status["tasks"] > 0
