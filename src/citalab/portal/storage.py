"""Persistencia local del portal: un único fichero SQLite con documentos JSON."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.RLock()
        with self._lock:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT NOT NULL,
                    csrf TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    updated_at TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, conversation_id TEXT, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                    actor TEXT, action TEXT NOT NULL, detail TEXT);
            """)

    # ------------------------------------------------------------------ kv
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO kv(key, value) VALUES(?, ?)",
                             (key, json.dumps(value, ensure_ascii=False, default=str)))

    def keys(self, prefix: str) -> list[str]:
        with self._lock:
            return [r[0] for r in self._db.execute("SELECT key FROM kv WHERE key LIKE ? ORDER BY key",
                                                   (prefix + "%",))]

    # --------------------------------------------------------------- tablas
    def save(self, table: str, key: str, data: dict, **columns: Any) -> None:
        names = ["id" if table != "users" else "username", *columns, "data"]
        values = [key, *columns.values(), json.dumps(data, ensure_ascii=False, default=str)]
        with self._lock:
            self._db.execute(f"INSERT OR REPLACE INTO {table}({','.join(names)}) VALUES({','.join('?' * len(names))})",
                             values)

    def load(self, table: str, key: str) -> dict | None:
        column = "username" if table == "users" else "id"
        with self._lock:
            row = self._db.execute(f"SELECT data FROM {table} WHERE {column}=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, table: str, key: str) -> None:
        with self._lock:
            self._db.execute(f"DELETE FROM {table} WHERE id=?", (key,))

    def all(self, table: str, where: str = "", params: tuple = ()) -> list[dict]:
        order = " ORDER BY updated_at DESC" if table == "conversations" else ""
        with self._lock:
            rows = self._db.execute(f"SELECT data FROM {table} {where}{order}", params).fetchall()
        return [json.loads(r[0]) for r in rows]

    # -------------------------------------------------------------- sesiones
    def create_session(self, token: str, username: str, csrf: str, expires: float) -> None:
        with self._lock:
            self._db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (token, username, csrf, expires))

    def session(self, token: str) -> tuple[str, str, float] | None:
        with self._lock:
            row = self._db.execute("SELECT username, csrf, expires FROM sessions WHERE token=?", (token,)).fetchone()
        return tuple(row) if row else None  # type: ignore[return-value]

    def drop_session(self, token: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM sessions WHERE token=?", (token,))

    # --------------------------------------------------------------- auditoría
    def audit(self, actor: str | None, action: str, detail: dict | None = None) -> None:
        with self._lock:
            self._db.execute("INSERT INTO audit(at, actor, action, detail) VALUES(?,?,?,?)",
                             (datetime.now(UTC).isoformat(), actor, action,
                              json.dumps(detail or {}, ensure_ascii=False, default=str)))

    def audit_rows(self, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id, at, actor, action, detail FROM audit ORDER BY id DESC LIMIT ?",
                                    (limit,)).fetchall()
        result = []
        for r in rows:
            detail = json.loads(r[4] or "{}")
            target = next((str(v) for k, v in detail.items() if k in ("id", "conversation", "slot", "appointment",
                                                                       "subject", "username")), "")
            result.append({"id": r[0], "at": r[1], "actor": r[2], "action": r[3], "target": target, "detail": detail})
        return result
