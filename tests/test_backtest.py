import csv

from pangan import backtest, features


def _write_dataset(path, rows):
    fields = ["month", "commodity_id", "n_obs", "mean", "last", "min", "max", "std", "mom_pct", "cpi_yoy"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _monthly_rows(months, cpi_values, mom="0.5"):
    rows = []
    for month, cpi in zip(months, cpi_values):
        for commodity in ("com_1", "com_2"):
            rows.append(
                {
                    "month": month,
                    "commodity_id": commodity,
                    "n_obs": "20",
                    "mean": "1",
                    "last": "1",
                    "min": "1",
                    "max": "1",
                    "std": "0",
                    "mom_pct": mom,
                    "cpi_yoy": cpi,
                }
            )
    return rows


def test_add_months():
    assert features.add_months("2024-01", -1) == "2023-12"
    assert features.add_months("2024-12", 1) == "2025-01"
    assert features.add_months("2024-06", 0) == "2024-06"


def test_load_dataset_aggregates_per_month(tmp_path):
    path = tmp_path / "d.csv"
    _write_dataset(
        path,
        _monthly_rows(["2024-01", "2024-02"], ["2.5", "2.6"], mom="1.0"),
    )

    panel = backtest.load_dataset(str(path))
    assert panel[0]["y"] == 2.5
    assert panel[0]["food_mom"] == 1.0
    assert panel[0]["y_lag1"] is None
    assert panel[1]["y_lag1"] == 2.5
    assert panel[1]["food_mom_3"] is None


def test_horizon_shifts_target(tmp_path):
    months = ["2024-01", "2024-02", "2024-03", "2024-04"]
    path = tmp_path / "d.csv"
    _write_dataset(path, _monthly_rows(months, ["1.0", "2.0", "3.0", "4.0"]))

    panel = backtest.load_dataset(str(path), horizon=1)
    assert [r["origin"] if "origin" in r else r["month"] for r in panel] == months[:3]
    assert panel[0]["target_month"] == "2024-02"
    assert panel[0]["y"] == 2.0
    assert panel[0]["y_lag1"] == 1.0
    assert panel[2]["y"] == 4.0
    assert panel[2]["y_lag1"] == 3.0


def test_rolling_uses_only_past_data():
    panel = [
        {
            "month": f"2020-{i + 1:02d}",
            "target_month": f"2020-{i + 1:02d}",
            "y": 2.0 + i * 0.1,
            "y_lag1": None if i == 0 else 2.0 + (i - 1) * 0.1,
            "food_mom": 0.2,
            "food_mom_3": 0.6,
        }
        for i in range(12)
    ]
    result = backtest.rolling(panel, min_train=5)
    assert [r["month"] for r in result] == [f"2020-{i + 1:02d}" for i in range(6, 12)]
    assert [r["n_train"] for r in result] == list(range(5, 11))


def test_metrics_math():
    rows = [
        {"y": 2.0, "pred_base": 1.0, "pred_feat": 3.0},
        {"y": 4.0, "pred_base": 3.0, "pred_feat": 5.0},
    ]
    base = backtest.metrics(rows, "pred_base")
    assert base == {"n": 2, "mae": 1.0, "rmse": 1.0, "bias": 1.0}
    feat = backtest.metrics(rows, "pred_feat")
    assert feat["bias"] == -1.0


def test_mae_diff_ci_sign():
    rows = [
        {"y": 2.0, "pred_base": 2.1, "pred_feat": 2.5},
        {"y": 4.0, "pred_base": 4.1, "pred_feat": 4.6},
    ]
    out = backtest.mae_diff_ci(rows, n_boot=100)
    assert out["diff"] > 0
    assert out["lo"] <= out["hi"]
