from pangan import publish

def _rows():
    return [
        {
            "month": "2024-01",
            "commodity_id": "com_1",
            "n_obs": "20",
            "mean": "100.0",
            "last": "101.0",
            "min": "99.0",
            "max": "102.0",
            "std": "1.0",
            "mom_pct": "",
            "food_mtm": "0.5",
            "headline_mtm": "0.3",
        },
        {
            "month": "2024-02",
            "commodity_id": "com_1",
            "n_obs": "18",
            "mean": "102.0",
            "last": "103.0",
            "min": "101.0",
            "max": "104.0",
            "std": "1.2",
            "mom_pct": "1.98",
            "food_mtm": "-0.2",
            "headline_mtm": "",
        },
        {
            "month": "2024-01",
            "commodity_id": "com_2",
            "n_obs": "21",
            "mean": "50.0",
            "last": "50.5",
            "min": "49.0",
            "max": "51.0",
            "std": "0.5",
            "mom_pct": "",
            "food_mtm": "0.5",
            "headline_mtm": "0.3",
        },
    ]

def test_summary_counts_months_commodities_and_missing():
    out = publish.summary(_rows())
    assert out["n_rows"] == 3
    assert out["months"] == ("2024-01", "2024-02")
    assert out["n_commodities"] == 2
    assert out["missing_target"] == 0
    assert out["missing_comparator"] == 1
    assert out["missing_mom"] == 2

def test_datasheet_names_sources_and_limits():
    text = publish.datasheet(publish.summary(_rows()), target="food_mtm")
    assert "PIHPS" in text
    assert "BPS" in text
    assert "food_mtm" in text
    assert "2024-01" in text and "2024-02" in text
    assert "Batasan" in text
    assert "tidak resmi" in text.lower()

def test_write_exports_csv_and_datasheet(tmp_path):
    csv_path, md_path = publish.write(_rows(), tmp_path)
    assert csv_path.exists() and md_path.exists()
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("month,commodity_id,")
    assert "datasheet" in md_path.name
    assert "2024-02" in md_path.read_text(encoding="utf-8")
