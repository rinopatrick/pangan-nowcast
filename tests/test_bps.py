import pytest

from pangan import bps


DOC_EXAMPLE = {
    "status": "OK",
    "var": [{"val": 145, "label": "Persentase Rumah Tangga", "unit": "Persen"}],
    "turvar": [{"val": 289, "label": "Listrik PLN"}],
    "vervar": [{"val": 9999, "label": "INDONESIA"}],
    "tahun": [{"val": 100, "label": "2000"}],
    "turtahun": [{"val": 0, "label": "Tahun"}],
    "datacontent": {"99991452891000": 83.68},
}


def _monthly_payload(values: dict[str, float]) -> dict:
    return {
        "status": "OK",
        "var": [{"val": 2223, "label": "Inflasi M-to-M", "unit": "Persen"}],
        "turvar": [{"val": 0, "label": "Umum"}, {"val": 1, "label": "Makanan"}],
        "vervar": [{"val": 9999, "label": "INDONESIA"}, {"val": 1100, "label": "ACEH"}],
        "tahun": [{"val": 123, "label": "2023"}],
        "turtahun": [{"val": 1, "label": "Januari"}, {"val": 2, "label": "Februari"}],
        "datacontent": values,
    }


def test_parse_documented_key_shape():
    rows = bps.parse_rows(DOC_EXAMPLE)
    assert rows == [
        {
            "vervar": "INDONESIA",
            "turvar": "Listrik PLN",
            "year": "2000",
            "subperiod": "Tahun",
            "value": 83.68,
        }
    ]


def test_monthly_series_filters_vervar_and_turvar():
    # key = vervar + var + turvar + tahun + turtahun
    values = {
        "9999222301231": 0.5,  # INDONESIA, Umum, 2023, Januari
        "9999222301232": 0.7,  # INDONESIA, Umum, 2023, Februari
        "9999222311231": 1.5,  # INDONESIA, Makanan, 2023, Januari
        "1100222301231": 0.9,  # ACEH, Umum, 2023, Januari
    }
    payload = _monthly_payload(values)

    umum = bps.monthly_series(payload, turvar="Umum")
    assert umum == [{"month": "2023-01", "value": 0.5}, {"month": "2023-02", "value": 0.7}]

    makanan = bps.monthly_series(payload, turvar="Makanan")
    assert makanan == [{"month": "2023-01", "value": 1.5}]


def test_month_from_label():
    assert bps.month_from_label("Juli") == 7
    assert bps.month_from_label("Desember") == 12
    assert bps.month_from_label("03") == 3
    assert bps.month_from_label("Tahun") is None


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv(bps.ENV_KEY, raising=False)
    with pytest.raises(bps.BpsError, match=bps.ENV_KEY):
        bps.api_key()


def test_dotenv_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv(bps.ENV_KEY, raising=False)
    (tmp_path / ".env").write_text("BPS_API_KEY=abc123\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert bps.api_key() == "abc123"


def test_env_var_wins_over_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("BPS_API_KEY=fromfile\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(bps.ENV_KEY, "fromenv")
    assert bps.api_key() == "fromenv"
