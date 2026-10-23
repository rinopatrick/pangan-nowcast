"""Target makro: inflasi umum Indonesia year-on-year (persen).

Sumber: FRED, seri CPALTT01IDM659N (OECD MEI). Tanpa API key.
Seri ini YoY, bukan m-to-m: nilai 2024-01 = 2,57 cocok dengan inflasi YoY resmi.
FRED mengikuti jadwal OECD, jadi beberapa bulan terakhir bisa tertinggal.
Untuk m-to-m dan kelompok makanan, BPS WebAPI butuh API key
(https://webapi.bps.go.id/developer/).
"""

from __future__ import annotations

import sqlite3

import requests

SERIES = "CPALTT01IDM659N"
URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES}"


def parse_csv(text: str, series: str = SERIES) -> list[tuple[str, str, float]]:
    rows = []
    lines = text.splitlines()[1:]
    for line in lines:
        parts = line.strip().split(",")
        if len(parts) < 2:
            continue
        date, raw = parts[0], parts[1]
        if not date or raw in {"", ".", "NaN"}:
            continue
        rows.append((series, date[:7], float(raw)))
    return rows


def fetch() -> list[tuple[str, str, float]]:
    r = requests.get(URL, timeout=60)
    r.raise_for_status()
    return parse_csv(r.text)


def save(con: sqlite3.Connection, rows: list[tuple[str, str, float]]) -> int:
    con.execute(
        "CREATE TABLE IF NOT EXISTS macro ("
        "series TEXT NOT NULL, month TEXT NOT NULL, value REAL, PRIMARY KEY (series, month))"
    )
    con.executemany("INSERT OR REPLACE INTO macro (series, month, value) VALUES (?, ?, ?)", rows)
    con.commit()
    return len(rows)


def load(con: sqlite3.Connection, series: str = SERIES) -> dict[str, float]:
    try:
        cur = con.execute("SELECT month, value FROM macro WHERE series = ?", (series,))
    except sqlite3.OperationalError:
        return {}
    return dict(cur.fetchall())
