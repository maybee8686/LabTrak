"""Хранилище данных LabTrack (SQLite)."""
import os
import sqlite3
import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS labs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    subject TEXT DEFAULT '',
    deadline TEXT DEFAULT '',
    description TEXT DEFAULT '',
    x_name TEXT DEFAULT '', x_unit TEXT DEFAULT '',
    y_name TEXT DEFAULT '', y_unit TEXT DEFAULT '',
    conclusion TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lab_id INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    done INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lab_id INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    x REAL NOT NULL,
    y REAL NOT NULL
);
"""

LAB_FIELDS = {"title", "subject", "deadline", "description", "x_name",
              "x_unit", "y_name", "y_unit", "conclusion"}


def default_path():
    base = os.environ.get("APPDATA") or str(Path.home())
    folder = Path(base) / "LabTrack"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "labtrack.db"


class Database:
    def __init__(self, path=None):
        self.conn = sqlite3.connect(str(path or default_path()))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    # --- лабораторные работы ---
    def add_lab(self, title):
        cur = self.conn.execute(
            "INSERT INTO labs (title, created_at) VALUES (?, ?)",
            (title, datetime.date.today().isoformat()))
        self.conn.commit()
        return cur.lastrowid

    def get_lab(self, lab_id):
        row = self.conn.execute("SELECT * FROM labs WHERE id=?", (lab_id,)).fetchone()
        return dict(row) if row else None

    def list_labs(self):
        rows = self.conn.execute("SELECT * FROM labs ORDER BY id DESC").fetchall()
        result = []
        for r in rows:
            lab = dict(r)
            lab["done"], lab["total"] = self.progress(lab["id"])
            result.append(lab)
        return result

    def update_lab(self, lab_id, **fields):
        fields = {k: v for k, v in fields.items() if k in LAB_FIELDS}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE labs SET {sets} WHERE id=?",
                          (*fields.values(), lab_id))
        self.conn.commit()

    def delete_lab(self, lab_id):
        self.conn.execute("DELETE FROM labs WHERE id=?", (lab_id,))
        self.conn.commit()

    # --- этапы ---
    def add_step(self, lab_id, title):
        pos = self.conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM steps WHERE lab_id=?",
            (lab_id,)).fetchone()[0]
        self.conn.execute(
            "INSERT INTO steps (lab_id, title, position) VALUES (?, ?, ?)",
            (lab_id, title, pos))
        self.conn.commit()

    def list_steps(self, lab_id):
        rows = self.conn.execute(
            "SELECT * FROM steps WHERE lab_id=? ORDER BY position, id", (lab_id,))
        return [dict(r) for r in rows]

    def toggle_step(self, step_id):
        self.conn.execute("UPDATE steps SET done = 1 - done WHERE id=?", (step_id,))
        self.conn.commit()

    def delete_step(self, step_id):
        self.conn.execute("DELETE FROM steps WHERE id=?", (step_id,))
        self.conn.commit()

    def progress(self, lab_id):
        done, total = self.conn.execute(
            "SELECT COALESCE(SUM(done), 0), COUNT(*) FROM steps WHERE lab_id=?",
            (lab_id,)).fetchone()
        return int(done), int(total)

    # --- измерения ---
    def add_measurements(self, lab_id, pairs):
        self.conn.executemany(
            "INSERT INTO measurements (lab_id, x, y) VALUES (?, ?, ?)",
            [(lab_id, x, y) for x, y in pairs])
        self.conn.commit()

    def list_measurements(self, lab_id):
        rows = self.conn.execute(
            "SELECT * FROM measurements WHERE lab_id=? ORDER BY id", (lab_id,))
        return [dict(r) for r in rows]

    def delete_measurement(self, m_id):
        self.conn.execute("DELETE FROM measurements WHERE id=?", (m_id,))
        self.conn.commit()
