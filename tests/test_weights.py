from pangan import weights

def test_mapping_covers_each_commodity_once():
    seen = [c for _, _, ids in weights.CATEGORIES for c in ids]
    assert len(seen) == len(set(seen)) == 21
    assert set(seen) == {f"com_{i}" for i in range(1, 22)}

def test_coverage_matches_national_basket():
    assert round(weights.COVERAGE, 4) == 9.6964
    assert round(weights.COVERAGE / weights.FOOD_GROUP, 4) == 0.3463

def test_weighted_mom_weights_categories():
    monthly = {
        ("com_11", "2024-01"): {"mom_pct": 10.0},  # BAWANG MERAH, 0.5098
        ("com_12", "2024-01"): {"mom_pct": 0.0},  # BAWANG PUTIH, 0.3173
        ("com_13", "2024-01"): {"mom_pct": 5.0},  # CABAI MERAH, 0.4485
    }
    out = weights.weighted_mom(monthly)
    expected = (10.0 * 0.5098 + 0.0 * 0.3173 + 5.0 * 0.4485) / (0.5098 + 0.3173 + 0.4485)
    assert round(out["2024-01"], 6) == round(expected, 6)

def test_weighted_mom_skips_missing_commodity():
    monthly = {
        ("com_11", "2024-01"): {"mom_pct": 10.0},
        ("com_12", "2024-01"): {"mom_pct": None},
    }
    out = weights.weighted_mom(monthly)
    assert out["2024-01"] == 10.0

def test_weighted_mom_averages_grades_within_category():
    monthly = {
        ("com_1", "2024-01"): {"mom_pct": 2.0},
        ("com_2", "2024-01"): {"mom_pct": 4.0},
    }
    out = weights.weighted_mom(monthly)
    assert out["2024-01"] == 3.0

def test_weighted_mom_empty_month_is_none():
    assert weights.weighted_mom({}) == {}
