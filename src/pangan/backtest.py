"""Backtest rolling-origin: AR(1) vs AR(1) + fitur harga pangan.

Target: inflasi umum YoY bulan t. Fitur harga bulan t sudah diketahui pada akhir
bulan t (CPI baru rilis awal bulan t+1), jadi ini nowcast, bukan ramalan ke depan.
"""

from __future__ import annotations

import csv
import math
import statistics

from .features import prev_month

TARGET = "cpi_yoy"
FEATURES = ["food_mom", "food_mom_3"]


def load_dataset(path: str, target: str = TARGET) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    by_month: dict[str, list[dict]] = {}
    for row in rows:
        by_month.setdefault(row["month"], []).append(row)

    months = sorted(by_month)
    cpi = {}
    mom = {}
    for month in months:
        targets = [float(r[target]) for r in by_month[month] if r[target] not in ("", None)]
        cpi[month] = targets[0] if targets else None
        moms = [float(r["mom_pct"]) for r in by_month[month] if r["mom_pct"] not in ("", None)]
        mom[month] = statistics.fmean(moms) if moms else None

    panel = []
    for i, month in enumerate(months):
        prev = months[i - 1] if i else None
        consecutive = prev is not None and prev == prev_month(month)
        window = [mom.get(prev_month(month)), mom.get(prev_month(prev_month(month))), mom.get(month)]
        panel.append(
            {
                "month": month,
                target: cpi[month],
                "y_lag1": cpi.get(prev) if consecutive else None,
                "food_mom": mom[month],
                "food_mom_3": sum(window) if all(v is not None for v in window) else None,
                "n_commodities": len(by_month[month]),
            }
        )
    return panel


def _fit_predict(train: list[dict], row: dict, cols: list[str], target: str = TARGET) -> float:
    import numpy as np

    keys = ["y_lag1", *cols]
    X = np.array([[1.0, *(r[k] for k in keys)] for r in train])
    y = np.array([r[target] for r in train])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    x = np.array([1.0, *(row[k] for k in keys)])
    return float(x @ beta)


def rolling(
    panel: list[dict], cols: list[str] = FEATURES, min_train: int = 30, target: str = TARGET
) -> list[dict]:
    """Untuk tiap bulan uji, model hanya melihat data sebelum bulan itu."""
    out = []
    for i, row in enumerate(panel):
        needed = ["y_lag1", *cols]
        if row[target] is None or any(row[k] is None for k in needed):
            continue
        train = [
            r for r in panel[:i] if r[target] is not None and all(r[k] is not None for k in needed)
        ]
        if len(train) < min_train:
            continue
        out.append(
            {
                "month": row["month"],
                "y": row[target],
                "pred_base": row["y_lag1"],
                "pred_ar": _fit_predict(train, row, [], target),
                "pred_feat": _fit_predict(train, row, cols, target),
                "n_train": len(train),
            }
        )
    return out


def metrics(rows: list[dict], key: str) -> dict:
    errs = [r["y"] - r[key] for r in rows]
    n = len(errs)
    return {
        "n": n,
        "mae": sum(abs(e) for e in errs) / n,
        "rmse": math.sqrt(sum(e * e for e in errs) / n),
        "bias": sum(errs) / n,
    }


def mae_diff_ci(
    rows: list[dict], base: str = "pred_base", feat: str = "pred_feat", n_boot: int = 5000, seed: int = 0
) -> dict:
    """Selisih MAE(feat) - MAE(base) + CI bootstrap 95%. Positif = fitur lebih buruk."""
    import numpy as np

    diff = np.array([abs(r["y"] - r[feat]) - abs(r["y"] - r[base]) for r in rows])
    rng = np.random.default_rng(seed)
    sample = diff[rng.integers(0, len(diff), size=(n_boot, len(diff)))].mean(axis=1)
    return {
        "diff": float(diff.mean()),
        "lo": float(np.percentile(sample, 2.5)),
        "hi": float(np.percentile(sample, 97.5)),
    }
