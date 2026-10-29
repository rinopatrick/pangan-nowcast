"""Agregasi harga harian -> fitur bulanan, lalu join dengan inflasi bulanan."""

from __future__ import annotations

import statistics

from . import weights

MONTH_FIELDS = ["n_obs", "mean", "last", "min", "max", "std", "mom_pct", "mom_mean"]
DERIVED_FIELDS = ["mom_mean_3", "mom_weighted", "mom_weighted_3"]


def add_months(month: str, delta: int) -> str:
    year, mon = (int(x) for x in month.split("-"))
    total = year * 12 + (mon - 1) + delta
    return f"{total // 12}-{total % 12 + 1:02d}"


def prev_month(month: str) -> str:
    return add_months(month, -1)


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
        row["mom_mean"] = (
            (row["mean"] / prev["mean"] - 1.0) * 100.0 if prev and prev["mean"] else None
        )
    return out


def build_dataset(
    prices: list[tuple[str, str, float | None]],
    target: dict[str, float],
    target_name: str = "cpi_yoy",
    extras: dict[str, dict[str, float]] | None = None,
    weighted: bool = True,
    as_of_day: int | None = None,
) -> list[dict]:
    """`extras` = {nama kolom: {month: nilai}}. Nilai hilang menjadi None.

    `as_of_day` memotong setiap bulan pada tanggal itu (mis. 15), sehingga
    statistik bulan t dan t-1 sama-sama memakai jendela hari 1..as_of_day.
    Ini yang membuat nowcast tengah bulan sebanding antar bulan.
    `weighted=True` menambah `mom_weighted` dan `mom_weighted_3` memakai bobot
    IHK nasional dari `pangan.weights`.
    """
    extras = extras or {}
    if as_of_day is not None:
        prices = [p for p in prices if int(p[1][8:10]) <= as_of_day]
    monthly_rows = monthly(prices)
    weighted_mom = weights.weighted_mom(monthly_rows, field="mom_mean") if weighted else {}
    rows = []
    for (commodity_id, month), feats in sorted(monthly_rows.items()):
        row = {
            "month": month,
            "commodity_id": commodity_id,
            **feats,
            target_name: target.get(month),
            **{name: values.get(month) for name, values in extras.items()},
        }
        if weighted:
            window = [
                weighted_mom.get(add_months(month, -1)),
                weighted_mom.get(add_months(month, -2)),
                weighted_mom.get(month),
            ]
            row["mom_weighted"] = weighted_mom.get(month)
            row["mom_weighted_3"] = (
                sum(window) if all(v is not None for v in window) else None
            )
        mean_window = [
            monthly_rows.get((commodity_id, add_months(month, -1)), {}).get("mom_mean"),
            monthly_rows.get((commodity_id, add_months(month, -2)), {}).get("mom_mean"),
            feats["mom_mean"],
        ]
        row["mom_mean_3"] = (
            sum(mean_window) if all(v is not None for v in mean_window) else None
        )
        rows.append(row)
    return rows
