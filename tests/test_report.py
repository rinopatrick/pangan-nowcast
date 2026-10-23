from pangan import backtest, report

def _rows(headline=False):
    panel = [
        {
            "month": f"2024-{i + 1:02d}",
            "target_month": f"2024-{i + 1:02d}",
            "y": 1.0 + i * 0.1,
            "y_lag1": 0.9 + i * 0.1,
            "food_mom": 0.1,
            "food_mom_3": 0.3,
        }
        for i in range(6)
    ]
    if headline:
        for i, row in enumerate(panel):
            row["headline_mtm"] = 0.2 + i * 0.05
    return backtest.rolling(panel, min_train=2)

def test_metrics_table_marks_best_model():
    html = report.metrics_table(_rows())
    assert "<table>" in html
    assert "AR(1)+harga" in html
    assert 'class="best"' in html

def test_svg_chart_has_lines_for_all_models():
    svg = report.svg_chart(_rows())
    assert svg.startswith("<svg")
    assert svg.count("<polyline") == 4
    assert "2024-03" in svg

def test_svg_chart_adds_headline_line_when_available():
    svg = report.svg_chart(_rows(headline=True))
    assert svg.count("<polyline") == 5
    assert "AR(1)+headline" in svg

def test_build_report_contains_ci_and_period():
    html = report.build_report(_rows(), "food_mtm", 0, "data/x.csv", 2)
    assert "Nowcast food_mtm" in html
    assert "95% CI" in html
    assert "2024-03 s/d 2024-06" in html
