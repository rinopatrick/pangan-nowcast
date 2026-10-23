import csv

from pangan import backtest, features


def _write_dataset(path, rows, extra_fields=()):
    fields = [
        "month",
        "commodity_id",
        "n_obs",
        "mean",
        "last",
        "min",
        "max",
        "std",
        "mom_pct",
        "cpi_yoy",
        *extra_fields,
    ]
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

def test_load_dataset_reads_headline_column(tmp_path):
    path = tmp_path / "d.csv"
    rows = _monthly_rows(["2024-01", "2024-02"], ["2.5", "2.6"])
    for row in rows:
        row["headline_mtm"] = "0.3" if row["month"] == "2024-01" else ""
    _write_dataset(path, rows, extra_fields=("headline_mtm",))

    panel = backtest.load_dataset(str(path))
    assert panel[0]["headline_mtm"] == 0.3
    assert panel[1]["headline_mtm"] is None

def _headline_panel(last_y=3.0, last_headline=0.9):
    panel = []
    for i in range(12):
        panel.append(
            {
                "month": f"2020-{i + 1:02d}",
                "target_month": f"2020-{i + 1:02d}",
                "y": 2.0 + i * 0.1 if i < 11 else last_y,
                "y_lag1": None if i == 0 else 2.0 + (i - 1) * 0.1,
                "food_mom": 0.2,
                "food_mom_3": 0.6,
                "headline_mtm": 0.5 + i * 0.01 if i < 11 else last_headline,
            }
        )
    return panel

def test_rolling_adds_headline_prediction():
    result = backtest.rolling(_headline_panel(), min_train=5)
    assert result
    assert all(isinstance(r["pred_headline"], float) for r in result)

def test_rolling_headline_uses_only_past_data():
    base = backtest.rolling(_headline_panel(), min_train=5)
    changed = backtest.rolling(_headline_panel(last_y=5.0, last_headline=1.5), min_train=5)
    assert [r["pred_headline"] for r in base[:-1]] == [
        r["pred_headline"] for r in changed[:-1]
    ]
    assert base[-1]["pred_headline"] != changed[-1]["pred_headline"]

def test_rolling_without_headline_sets_none():
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
    assert all(r["pred_headline"] is None for r in result)
    assert all(r["pred_headline_feat"] is None for r in result)

def test_rolling_adds_nested_headline_plus_price():
    result = backtest.rolling(_headline_panel(), min_train=5)
    assert result
    assert all(isinstance(r["pred_headline_feat"], float) for r in result)
    assert all(r["pred_headline_feat"] != r["pred_headline"] for r in result)

def test_dm_test_no_difference():
    rows = [{"y": 1.0, "base": 1.0, "feat": 1.0} for _ in range(40)]
    out = backtest.dm_test(rows, base="base", feat="feat")
    assert out["diff"] == 0.0
    assert out["stat"] == 0.0
    assert out["p_value"] == 1.0

def test_dm_test_detects_clear_improvement():
    rows = [
        {"y": 1.0, "base": 1.0 + (i % 3) * 0.1, "feat": 1.0 + (i % 5) * 0.01}
        for i in range(40)
    ]
    out = backtest.dm_test(rows, base="base", feat="feat")
    assert out["diff"] < 0
    assert out["stat"] < -3
    assert out["p_value"] < 0.01

def test_dm_test_sign_is_feat_minus_base():
    rows = [
        {"y": 1.0, "base": 1.0 + (i % 5) * 0.01, "feat": 1.0 + (i % 3) * 0.1}
        for i in range(40)
    ]
    out = backtest.dm_test(rows, base="base", feat="feat")
    assert out["diff"] > 0
    assert out["stat"] > 3

def test_dm_test_constant_nonzero_difference_is_infinite():
    rows = [{"y": 1.0, "base": 0.0, "feat": 1.0} for _ in range(40)]
    out = backtest.dm_test(rows, base="base", feat="feat")
    assert out["diff"] == -1.0
    assert out["stat"] == float("-inf")
    assert out["p_value"] == 0.0
