"""Agregasi harga harian -> fitur bulanan, lalu join dengan inflasi bulanan."""

from __future__ import annotations

import statistics

MONTH_FIELDS = ["n_obs", "mean", "last", "min", "max", "std", "mom_pct"]


def prev_month(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"


def monthly(prices: list[tuple[str, str, float | None]]) -> dict[tuple[str, str], dict]:
    """prices: (commodity_id, date, value) -> {(commodity, month): fitur}."""
    groups: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for commodity_id, date, value in prices:
        if value is None:
            continue
        groups.setdefault((commodity_id, date[:7]), []).append((date, value))

    out: dict[tuple[str, str], dict] = {}
    for (commodity_id, month), points in groups.items():
        points.sort()
        values = [v for _, v in points]
        out[(commodity_id, month)] = {
            "n_obs": len(values),
            "mean": statistics.fmean(values),
            "last": values[-1],
            "min": min(values),
            "max": max(values),
            "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
        }

    for (commodity_id, month), row in out.items():
        prev = out.get((commodity_id, prev_month(month)))
        row["mom_pct"] = (
            (row["last"] / prev["last"] - 1.0) * 100.0 if prev and prev["last"] else None
        )
    return out


def build_dataset(
    prices: list[tuple[str, str, float | None]], cpi: dict[str, float]
) -> list[dict]:
    rows = []
    for (commodity_id, month), feats in sorted(monthly(prices).items()):
        rows.append({"month": month, "commodity_id": commodity_id, **feats, "cpi_yoy": cpi.get(month)})
    return rows
