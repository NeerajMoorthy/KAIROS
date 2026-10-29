"""
User accounts: sign up, log in, and a private workspace for each user.

* Users and login sessions live in the project's own HashTable (separate
  chaining, djb2), keyed by username and by a SHA-256 digest of the session
  token. The raw token is only ever held by the browser.
* Passwords are stored as PBKDF2-HMAC-SHA256 hashes with a per-user salt.
* Each user gets their own KairosStore, loaded on first use and saved after
  every change, so one person's tasks never appear in another's account.

Everything is persisted through services.storage (files locally, Postgres
when KAIROS_DATABASE_URL is set).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ..ds.hash_table import HashTable
from . import persistence
from .storage import Storage
from .store import KairosStore

PBKDF2_ITERATIONS = 200_000
SESSION_DAYS = 30
USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8
ACCOUNTS_KEY = "accounts"


class AccountError(ValueError):
    """A sign-up or log-in problem worth showing to the user."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_username(username: str) -> str:
    return username.strip().lower()


class AccountService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self._lock = threading.RLock()
        self.users = HashTable(name="users")          # username -> user record
        self.sessions = HashTable(name="sessions")    # token digest -> session
        self._workspaces: Dict[str, KairosStore] = {}
        self._load()

    # ------------------------------------------------------------ persistence
    def _load(self) -> None:
        data = self.storage.read(ACCOUNTS_KEY) or {}
        for user in data.get("users", []):
            self.users.insert(user["username"], user)
        now = _now().isoformat()
        for session in data.get("sessions", []):
            if session.get("expires_at", "") > now:
                self.sessions.insert(session["digest"], session)

    def _save(self) -> None:
        self.storage.write(ACCOUNTS_KEY, {
            "users": self.users.values(),
            "sessions": self.sessions.values(),
        })

    # ------------------------------------------------------------- accounts
    def sign_up(self, username: str, password: str) -> Dict[str, Any]:
        username = normalize_username(username)
        if not USERNAME_RE.match(username):
            raise AccountError("Usernames are 3–32 characters: letters, numbers, dots, dashes or underscores.")
        if len(password) < MIN_PASSWORD:
            raise AccountError(f"Passwords need at least {MIN_PASSWORD} characters.")
        with self._lock:
            if self.users.contains(username):
                raise AccountError("That username is taken.")
            salt = secrets.token_bytes(16)
            self.users.insert(username, {
                "username": username,
                "salt": salt.hex(),
                "password_hash": _hash_password(password, salt),
                "created_at": _now().isoformat(timespec="seconds"),
            })
            return self._start_session(username)

    def log_in(self, username: str, password: str) -> Dict[str, Any]:
        username = normalize_username(username)
        user = self.users.get(username)
        # compare against a dummy hash for unknown users so both paths take
        # the same time and don't reveal which usernames exist
        salt = bytes.fromhex(user["salt"]) if user else b"kairos-no-user!!"
        expected = user["password_hash"] if user else ""
        if not hmac.compare_digest(_hash_password(password, salt), expected):
            raise AccountError("Wrong username or password.")
        with self._lock:
            return self._start_session(username)

    def _start_session(self, username: str) -> Dict[str, Any]:
        token = secrets.token_urlsafe(32)
        self.sessions.insert(_token_digest(token), {
            "digest": _token_digest(token),
            "username": username,
            "expires_at": (_now() + timedelta(days=SESSION_DAYS)).isoformat(),
        })
        self._save()
        return {"token": token, "username": username}

    def log_out(self, token: str) -> None:
        with self._lock:
            if self.sessions.delete(_token_digest(token)):
                self._save()

    def user_for_token(self, token: str) -> Optional[str]:
        session = self.sessions.get(_token_digest(token))
        if not session:
            return None
        if session["expires_at"] <= _now().isoformat():
            with self._lock:
                self.sessions.delete(session["digest"])
            return None
        return session["username"]

    # ------------------------------------------------------------ workspaces
    def workspace(self, username: str) -> KairosStore:
        with self._lock:
            store = self._workspaces.get(username)
            if store is None:
                store = KairosStore()
                data = self.storage.read(f"workspace:{username}")
                if data:
                    persistence.apply_snapshot(store, data)
                self._workspaces[username] = store
            return store

    def save_workspace(self, username: str) -> Dict[str, Any]:
        store = self.workspace(username)
        data = persistence.snapshot(store)
        self.storage.write(f"workspace:{username}", data)
        return data

    def workspace_status(self, username: str) -> Dict[str, Any]:
        data = self.storage.read(f"workspace:{username}") or {}
        return {
            "path": f"Your account ({self.storage.describe()})",
            "account": username,
            "exists": bool(data),
            "readable": True,
            "saved_at": data.get("saved_at"),
            "tasks": len(data.get("tasks", [])),
            "resources": len(data.get("resources", [])),
            "autosave": {"enabled": True, "last_saved_at": data.get("saved_at"), "last_error": None, "saves": 0},
        }
