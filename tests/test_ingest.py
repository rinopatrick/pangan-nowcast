from pangan import pihps, store


PAYLOAD = {
    "data": [
        {
            "no": "I",
            "name": "Semua Provinsi",
            "level": 0,
            "02/01/2024": "14,550",
            "03/01/2024": "-",
        },
        {
            "no": "II",
            "name": "Aceh",
            "level": 1,
            "02/01/2024": "13,750",
            "03/01/2024": "13,800",
        },
    ]
}


def test_melt_parses_dates_and_missing_values():
    rows = pihps.melt(PAYLOAD, "com_1", 1)
    assert len(rows) == 4
    assert rows[0] == ("com_1", 1, "Semua Provinsi", "2024-01-02", 14550.0)
    assert rows[1] == ("com_1", 1, "Semua Provinsi", "2024-01-03", None)
    assert rows[3] == ("com_1", 1, "Aceh", "2024-01-03", 13800.0)


def test_melt_empty_payload():
    assert pihps.melt({"data": []}, "com_1", 1) == []


def test_store_is_idempotent(tmp_path):
    con = store.connect(tmp_path / "t.db")
    store.init(con)
    rows = pihps.melt(PAYLOAD, "com_1", 1)

    assert store.save_prices(con, rows) == 4
    assert store.save_prices(con, rows) == 4

    count = con.execute("SELECT count(*) FROM price").fetchone()[0]
    assert count == 4
    value = con.execute(
        "SELECT value FROM price WHERE province = 'Aceh' AND date = '2024-01-02'"
    ).fetchone()[0]
    assert value == 13750.0
