"""Client untuk tabel harga PIHPS di bi.go.id.

Endpoint ini tidak resmi/didokumentasikan. Parameter yang dipakai berasal dari
halaman https://www.bi.go.id/hargapangan/TabelHarga/PasarTradisionalKomoditas.

Bentuk respons GetGridDataKomoditas: baris = provinsi, kolom = tanggal (DD/MM/YYYY).
Nilai "-" berarti tidak ada pencatatan pada tanggal itu.
"""

from __future__ import annotations

import re
import time

import requests

BASE = "https://www.bi.go.id/hargapangan/WebSite/TabelHarga"
TABLE_PAGE = "https://www.bi.go.id/hargapangan/TabelHarga/PasarTradisionalKomoditas"
HEADERS = {
    "User-Agent": "pangan-nowcast/0.1 (riset; kontak: github)",
    "Referer": TABLE_PAGE,
    "X-Requested-With": "XMLHttpRequest",
}

_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


class PihpsError(RuntimeError):
    pass


def _get(path: str, **params) -> object:
    last: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, headers=HEADERS, timeout=60)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            time.sleep(2**attempt)
    raise PihpsError(f"gagal mengambil {path}: {last}")


def commodities() -> list[dict]:
    return _get("GetRefCommodityAndCategory")["data"]


def provinces() -> list[dict]:
    return _get("GetRefProvince")["data"]


def price_types() -> list[dict]:
    return _get("GetRefPriceType")["data"]


def grid(
    commodity_id: str,
    start: str,
    end: str,
    price_type_id: int = 1,
    province_id: str = "",
) -> dict:
    """Harga harian satu komoditas, semua provinsi, rentang [start, end]."""
    return _get(
        "GetGridDataKomoditas",
        price_type_id=price_type_id,
        comcat_id=commodity_id,
        province_id=province_id,
        regency_id="",
        showKota="false",
        showPasar="false",
        tipe_laporan=1,
        start_date=start,
        end_date=end,
    )


def parse_value(raw: object) -> float | None:
    text = str(raw).strip()
    if text in {"", "-", "None"}:
        return None
    return float(text.replace(",", ""))


def melt(payload: dict, commodity_id: str, price_type_id: int) -> list[tuple]:
    """Ubah tabel lebar jadi baris (commodity, price_type, province, date, value)."""
    rows = payload.get("data") or []
    if not rows:
        return []
    dates = [k for k in rows[0] if _DATE.match(k)]
    out = []
    for row in rows:
        province = row["name"]
        for key in dates:
            day, month, year = key.split("/")
            out.append(
                (
                    commodity_id,
                    price_type_id,
                    province,
                    f"{year}-{month}-{day}",
                    parse_value(row.get(key)),
                )
            )
    return out
