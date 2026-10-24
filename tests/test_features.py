from pangan import features, macro


def test_prev_month():
    assert features.prev_month("2024-01") == "2023-12"
    assert features.prev_month("2024-03") == "2024-02"


def test_monthly_aggregates_and_mom():
    prices = [
        ("com_1", "2024-01-02", 100.0),
        ("com_1", "2024-01-30", 110.0),
        ("com_1", "2024-02-29", 121.0),
        ("com_1", "2024-01-15", None),
    ]
    out = features.monthly(prices)

    jan = out[("com_1", "2024-01")]
    assert jan["n_obs"] == 2
    assert jan["mean"] == 105.0
    assert jan["last"] == 110.0
    assert jan["min"] == 100.0
    assert jan["max"] == 110.0
    assert jan["mom_pct"] is None
    assert jan["mom_mean"] is None

    feb = out[("com_1", "2024-02")]
    assert round(feb["mom_pct"], 6) == 10.0
    assert round(feb["mom_mean"], 6) == round((121.0 / 105.0 - 1) * 100, 6)


def test_build_dataset_joins_cpi_and_keeps_missing():
    prices = [("com_1", "2024-01-02", 100.0), ("com_1", "2024-02-02", 110.0)]
    rows = features.build_dataset(prices, {"2024-01": 0.57})
    assert [r["month"] for r in rows] == ["2024-01", "2024-02"]
    assert rows[0]["cpi_yoy"] == 0.57
    assert rows[1]["cpi_yoy"] is None


def test_macro_parse_csv_skips_missing():
    text = "observation_date,CPALTT01IDM659N\n2024-01-01,0.57\n2024-02-01,.\n2024-03-01,0.52\n"
    rows = macro.parse_csv(text)
    assert rows == [
        ("CPALTT01IDM659N", "2024-01", 0.57),
        ("CPALTT01IDM659N", "2024-03", 0.52),
    ]


def test_build_dataset_custom_target_name():
    rows = features.build_dataset([("com_1", "2024-01-02", 100.0)], {"2024-01": 1.2}, "food_mtm")
    assert rows[0]["food_mtm"] == 1.2

def test_build_dataset_extra_series():
    prices = [("com_1", "2024-01-02", 100.0), ("com_1", "2024-02-02", 110.0)]
    rows = features.build_dataset(
        prices,
        {"2024-01": 0.57},
        extras={"headline_mtm": {"2024-01": 0.35}},
    )
    assert rows[0]["headline_mtm"] == 0.35
    assert rows[1]["headline_mtm"] is None

def test_build_dataset_adds_weighted_mom():
    prices = [
        ("com_11", "2024-01-02", 100.0),
        ("com_11", "2024-02-02", 110.0),
        ("com_12", "2024-02-02", 50.0),
    ]
    rows = features.build_dataset(prices, {"2024-02": 0.4})
    feb = [r for r in rows if r["month"] == "2024-02"]
    assert feb[0]["mom_weighted"] == feb[1]["mom_weighted"]
    assert feb[0]["mom_weighted"] is not None
    assert rows[0]["mom_weighted"] is None
    assert "mom_weighted_3" in rows[0]

def test_build_dataset_adds_mean_features():
    prices = [
        ("com_1", "2024-01-02", 100.0),
        ("com_1", "2024-02-02", 110.0),
        ("com_1", "2024-03-02", 121.0),
        ("com_1", "2024-04-02", 133.1),
    ]
    rows = features.build_dataset(prices, {"2024-04": 0.2})
    assert rows[0]["mom_mean"] is None
    assert round(rows[1]["mom_mean"], 6) == 10.0
    assert rows[2]["mom_mean_3"] is None
    assert round(rows[3]["mom_mean_3"], 6) == 30.0
    assert rows[3]["mom_pct"] is not None
