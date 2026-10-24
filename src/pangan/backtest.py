"""Backtest rolling-origin: naive vs AR(1) vs AR(1) + fitur harga pangan.

`horizon=0` adalah nowcast: target bulan t, fitur harga bulan t (diketahui pada
akhir bulan t; CPI baru rilis awal bulan t+1). `horizon=1` adalah forecast satu
bulan ke depan: fitur bulan t, target bulan t+1.

`pred_headline` adalah pembanding: AR(1) + inflasi umum bulanan resmi BPS
(`headline_mtm`). Kolom itu opsional di dataset; tanpa kolom, `pred_headline`
bernilai None.
"""

from __future__ import annotations

import csv
import math
import statistics

from .features import add_months

TARGET = "cpi_yoy"
# default: m-to-m dari rata-rata harga bulanan (lebih tahan nilai basi)
FEATURES = ["food_mom_mean", "food_mom_mean_3"]
LAST_FEATURES = ["food_mom", "food_mom_3"]
WEIGHTED_FEATURES = ["mom_weighted", "mom_weighted_3"]
COMPARATOR = "headline_mtm"


def load_dataset(path: str, target: str = TARGET, horizon: int = 0) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    by_month: dict[str, list[dict]] = {}
    for row in rows:
        by_month.setdefault(row["month"], []).append(row)

    months = sorted(by_month)
    values: dict[str, float | None] = {}
    mom: dict[str, float | None] = {}
    mom_mean: dict[str, float | None] = {}
    comparator: dict[str, float | None] = {}
    weighted: dict[str, float | None] = {}
    weighted_3: dict[str, float | None] = {}
    has_comparator = any(COMPARATOR in row for row in rows)
    has_weighted = any("mom_weighted" in row for row in rows)
    has_mean = any("mom_mean" in row for row in rows)
    for month in months:
        picks = [r[target] for r in by_month[month] if r.get(target) not in ("", None)]
        values[month] = float(picks[0]) if picks else None
        moms = [float(r["mom_pct"]) for r in by_month[month] if r["mom_pct"] not in ("", None)]
        mom[month] = statistics.fmean(moms) if moms else None
        if has_mean:
            means = [
                float(r["mom_mean"])
                for r in by_month[month]
                if r.get("mom_mean") not in ("", None)
            ]
            mom_mean[month] = statistics.fmean(means) if means else None
        if has_comparator:
            refs = [
                r[COMPARATOR]
                for r in by_month[month]
                if r.get(COMPARATOR) not in ("", None)
            ]
            comparator[month] = float(refs[0]) if refs else None
        if has_weighted:
            for key, bucket in (("mom_weighted", weighted), ("mom_weighted_3", weighted_3)):
                refs = [r[key] for r in by_month[month] if r.get(key) not in ("", None)]
                bucket[month] = float(refs[0]) if refs else None

    panel = []
    for month in months:
        target_month = add_months(month, horizon)
        y = values.get(target_month)
        if y is None:
            continue
        window = [
            mom.get(add_months(month, -1)),
            mom.get(add_months(month, -2)),
            mom.get(month),
        ]
        mean_window = [
            mom_mean.get(add_months(month, -1)),
            mom_mean.get(add_months(month, -2)),
            mom_mean.get(month),
        ]
        panel.append(
            {
                "month": month,
                "target_month": target_month,
                "y": y,
                "y_lag1": values.get(add_months(target_month, -1)),
                "food_mom": mom[month],
                "food_mom_3": sum(window) if all(v is not None for v in window) else None,
                "food_mom_mean": mom_mean.get(month),
                "food_mom_mean_3": (
                    sum(mean_window) if all(v is not None for v in mean_window) else None
                ),
                "headline_mtm": comparator.get(month),
                "mom_weighted": weighted.get(month),
                "mom_weighted_3": weighted_3.get(month),
                "n_commodities": len(by_month[month]),
            }
        )
    return panel


def _fit_predict(train: list[dict], row: dict, cols: list[str]) -> float:
    import numpy as np

    keys = ["y_lag1", *cols]
    X = np.array([[1.0, *(r[k] for k in keys)] for r in train])
    y = np.array([r["y"] for r in train])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    x = np.array([1.0, *(row[k] for k in keys)])
    return float(x @ beta)


def rolling(panel: list[dict], cols: list[str] = FEATURES, min_train: int = 30) -> list[dict]:
    """Untuk tiap bulan uji, model hanya melihat data sebelum bulan itu.

    `pred_headline_feat` adalah uji bersarang: AR(1) + headline + fitur harga.
    Perbandingannya dengan `pred_headline` mengukur tambahan fitur harga setelah
    inflasi umum diketahui.
    """
    out = []
    for i, row in enumerate(panel):
        needed = ["y_lag1", *cols]
        if any(row.get(k) is None for k in needed):
            continue
        train = [r for r in panel[:i] if all(r.get(k) is not None for k in needed)]
        if len(train) < min_train:
            continue
        pred_headline = None
        pred_headline_feat = None
        pred_headline_feat_last = None
        pred_feat_last = None
        pred_weighted = None
        pred_headline_weighted = None
        if all(row.get(k) is not None for k in LAST_FEATURES):
            l_needed = ["y_lag1", *LAST_FEATURES]
            l_train = [
                r for r in panel[:i] if all(r.get(k) is not None for k in l_needed)
            ]
            if len(l_train) >= min_train:
                pred_feat_last = _fit_predict(l_train, row, LAST_FEATURES)
        if all(row.get(k) is not None for k in WEIGHTED_FEATURES):
            w_needed = ["y_lag1", *WEIGHTED_FEATURES]
            w_train = [
                r for r in panel[:i] if all(r.get(k) is not None for k in w_needed)
            ]
            if len(w_train) >= min_train:
                pred_weighted = _fit_predict(w_train, row, WEIGHTED_FEATURES)
        if row.get(COMPARATOR) is not None:
            cmp_needed = ["y_lag1", COMPARATOR]
            cmp_train = [
                r for r in panel[:i] if all(r.get(k) is not None for k in cmp_needed)
            ]
            if len(cmp_train) >= min_train:
                pred_headline = _fit_predict(cmp_train, row, [COMPARATOR])
            nested_needed = ["y_lag1", COMPARATOR, *cols]
            nested_train = [
                r for r in panel[:i] if all(r.get(k) is not None for k in nested_needed)
            ]
            if len(nested_train) >= min_train:
                pred_headline_feat = _fit_predict(
                    nested_train, row, [COMPARATOR, *cols]
                )
            if all(row.get(k) is not None for k in LAST_FEATURES):
                nested_last_needed = ["y_lag1", COMPARATOR, *LAST_FEATURES]
                nested_last_train = [
                    r
                    for r in panel[:i]
                    if all(r.get(k) is not None for k in nested_last_needed)
                ]
                if len(nested_last_train) >= min_train:
                    pred_headline_feat_last = _fit_predict(
                        nested_last_train, row, [COMPARATOR, *LAST_FEATURES]
                    )
            if all(row.get(k) is not None for k in WEIGHTED_FEATURES):
                hw_needed = ["y_lag1", COMPARATOR, *WEIGHTED_FEATURES]
                hw_train = [
                    r for r in panel[:i] if all(r.get(k) is not None for k in hw_needed)
                ]
                if len(hw_train) >= min_train:
                    pred_headline_weighted = _fit_predict(
                        hw_train, row, [COMPARATOR, *WEIGHTED_FEATURES]
                    )
        out.append(
            {
                "month": row["target_month"],
                "origin": row["month"],
                "y": row["y"],
                "pred_base": row["y_lag1"],
                "pred_ar": _fit_predict(train, row, []),
                "pred_feat": _fit_predict(train, row, cols),
                "pred_feat_last": pred_feat_last,
                "pred_headline": pred_headline,
                "pred_headline_feat": pred_headline_feat,
                "pred_headline_feat_last": pred_headline_feat_last,
                "pred_weighted": pred_weighted,
                "pred_headline_weighted": pred_headline_weighted,
                "n_train": len(train),
            }
        )
    return out

def with_predictions(rows: list[dict], keys: list[str]) -> list[dict]:
    """Subset baris yang semua prediksinya tersedia (untuk metrik yang setara)."""
    return [r for r in rows if all(r.get(k) is not None for k in keys)]


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
    rows: list[dict],
    base: str = "pred_base",
    feat: str = "pred_feat",
    n_boot: int = 5000,
    seed: int = 0,
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

def dm_test(
    rows: list[dict],
    base: str = "pred_ar",
    feat: str = "pred_feat",
    lag: int | None = None,
) -> dict:
    """Diebold-Mariano dengan varians Newey-West.

    `diff` = MAE(feat) - MAE(base); negatif berarti `feat` lebih baik.
    `stat` memakai tanda yang sama. `lag` default mengikuti aturan 4*(n/100)^(2/9).
    """
    d = [abs(r["y"] - r[feat]) - abs(r["y"] - r[base]) for r in rows]
    n = len(d)
    if n < 2:
        raise ValueError("dm_test butuh minimal 2 baris")
    mean = sum(d) / n
    if lag is None:
        lag = max(0, int(round(4 * (n / 100) ** (2 / 9))))
    lrv = sum((x - mean) ** 2 for x in d) / n
    for k in range(1, lag + 1):
        auto = sum((d[i] - mean) * (d[i - k] - mean) for i in range(k, n)) / n
        lrv += 2 * (1 - k / (lag + 1)) * auto
    if lrv <= 0:
        if mean == 0:
            return {"diff": mean, "stat": 0.0, "p_value": 1.0, "lag": lag, "n": n}
        stat = math.copysign(math.inf, mean)
        return {"diff": mean, "stat": stat, "p_value": 0.0, "lag": lag, "n": n}
    stat = mean / math.sqrt(lrv / n)
    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(stat) / math.sqrt(2))))
    return {"diff": mean, "stat": stat, "p_value": p_value, "lag": lag, "n": n}
