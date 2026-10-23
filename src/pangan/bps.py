"""Client BPS WebAPI (butuh API key gratis: https://webapi.bps.go.id/developer/).

Spesifikasi endpoint mengikuti https://webapi.bps.go.id/documentation/:
  GET /v1/api/list/model/data/domain/{domain}/var/{var}/key/{key}/
  GET /v1/api/list/model/var/domain/{domain}/key/{key}/

Respons data berisi `datacontent` yang key-nya gabungan id:
vervar + var + turvar + tahun + turtahun.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

BASE = "https://webapi.bps.go.id/v1/api"
ENV_KEY = "BPS_API_KEY"

_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}


class BpsError(RuntimeError):
    pass


def _read_dotenv(path: str | Path = ".env") -> dict[str, str]:
    """Baca KEY=VALUE sederhana. Baris kosong dan komentar diabaikan."""
    values = {}
    file = Path(path)
    if not file.is_file():
        return values
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def api_key() -> str:
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        key = _read_dotenv().get(ENV_KEY, "").strip()
    if not key:
        raise BpsError(
            f"{ENV_KEY} belum diset. Daftar gratis di https://webapi.bps.go.id/developer/, "
            f"lalu set environment variable {ENV_KEY} atau taruh di file .env."
        )
    return key


def _get(path: str) -> dict:
    r = requests.get(f"{BASE}/{path}", timeout=90)
    r.raise_for_status()
    payload = r.json()
    status = str(payload.get("status", "")).lower()
    if status != "ok":
        raise BpsError(f"BPS menolak permintaan: {payload.get('message') or payload.get('status')}")
    return payload


def list_vars(subject: int | None = None, page: int = 1, domain: str = "0000") -> dict:
    parts = ["list", "model", "var", "domain", domain]
    if subject is not None:
        parts += ["subject", str(subject)]
    parts += ["page", str(page), "key", api_key()]
    return _get("/".join(parts))


def fetch_data(var_id: int, domain: str = "0000") -> dict:
    """Ambil semua kombinasi untuk satu variabel (tanpa filter vervar/tahun)."""
    parts = ["list", "model", "data", "domain", domain, "var", str(var_id), "key", api_key()]
    return _get("/".join(parts))


def _key_map(payload: dict) -> dict[str, tuple[int, int, int, int, int]]:
    """BPS menggabungkan id tanpa padding: vervar+var+turvar+tahun+turtahun."""
    var_id = payload["var"][0]["val"]
    vervar = payload.get("vervar") or [{"val": 0}]
    turvar = payload.get("turvar") or [{"val": 0}]
    tahun = payload.get("tahun") or [{"val": 0}]
    turtahun = payload.get("turtahun") or [{"val": 0}]
    mapping = {}
    for vv in vervar:
        for tv in turvar:
            for th in tahun:
                for tt in turtahun:
                    key = f"{vv['val']}{var_id}{tv['val']}{th['val']}{tt['val']}"
                    mapping[key] = (vv["val"], var_id, tv["val"], th["val"], tt["val"])
    return mapping


def _label(entries: list[dict], value: int) -> str:
    for entry in entries:
        if entry["val"] == value:
            return str(entry["label"])
    return str(value)


def parse_rows(payload: dict) -> list[dict]:
    """Baris datar: vervar, turvar, year, subperiod (label), value."""
    mapping = _key_map(payload)
    rows = []
    for key, value in (payload.get("datacontent") or {}).items():
        parts = mapping.get(str(key))
        if parts is None:
            continue
        vervar, _, turvar, year, turth = parts
        rows.append(
            {
                "vervar": _label(payload.get("vervar") or [], vervar),
                "turvar": _label(payload.get("turvar") or [], turvar),
                "year": _label(payload.get("tahun") or [], year),
                "subperiod": _label(payload.get("turtahun") or [], turth),
                "value": float(value),
            }
        )
    return rows


def month_from_label(label: str) -> int | None:
    text = label.strip().lower()
    if text.isdigit():
        return int(text)
    for name, number in _MONTHS.items():
        if text.startswith(name[:3]):
            return number
    return None


def monthly_series(payload: dict, vervar: str = "INDONESIA", turvar: str | None = None) -> list[dict]:
    rows = []
    for row in parse_rows(payload):
        if row["vervar"].casefold() != vervar.casefold():
            continue
        if turvar is not None and row["turvar"].casefold() != turvar.casefold():
            continue
        month = month_from_label(row["subperiod"])
        year = row["year"][:4]
        if month is None or not year.isdigit():
            continue
        rows.append({"month": f"{year}-{month:02d}", "value": row["value"]})
    return sorted(rows, key=lambda r: r["month"])
