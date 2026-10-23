"""Penyimpanan SQLite. Idempoten: ingest ulang rentang yang sama tidak menduplikasi."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS commodity (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category_id TEXT,
    denomination TEXT
);
CREATE TABLE IF NOT EXISTS province (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_type (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price (
    commodity_id TEXT NOT NULL,
    price_type_id INTEGER NOT NULL,
    province TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (commodity_id, price_type_id, province, date)
);
CREATE INDEX IF NOT EXISTS price_date ON price (date);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)


def save_refs(
    con: sqlite3.Connection,
    commodities: list[dict],
    provinces: list[dict],
    price_types: list[dict],
) -> int:
    con.executemany(
        "INSERT OR REPLACE INTO commodity (id, name, category_id, denomination) VALUES (?, ?, ?, ?)",
        [(c["id"], c["name"], c.get("cat_id"), c.get("denomination")) for c in commodities],
    )
    con.executemany(
        "INSERT OR REPLACE INTO province (id, name) VALUES (?, ?)",
        [(p["id"], p["name"]) for p in provinces],
    )
    con.executemany(
        "INSERT OR REPLACE INTO price_type (id, name) VALUES (?, ?)",
        [(t["id"], t["name"]) for t in price_types],
    )
    con.commit()
    return len(commodities) + len(provinces) + len(price_types)


def save_prices(con: sqlite3.Connection, rows: list[tuple]) -> int:
    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO price (commodity_id, price_type_id, province, date, value)"
        " VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)
