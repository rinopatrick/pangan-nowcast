"""Laporan HTML mandiri: tabel metrik + grafik prediksi (SVG inline, tanpa dependensi)."""

from __future__ import annotations

from . import backtest

MODELS = [
    ("pred_base", "naive", "#9aa0a6"),
    ("pred_ar", "AR(1)", "#1a73e8"),
    ("pred_feat", "AR(1)+harga", "#d93025"),
    ("pred_headline", "AR(1)+headline", "#188038"),
]

def available_models(rows: list[dict]) -> list[tuple[str, str, str]]:
    """Model yang punya prediksi untuk semua baris (kolom opsional bisa kosong)."""
    return [m for m in MODELS if all(r.get(m[0]) is not None for r in rows)]

_STYLE = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:32px auto;
max-width:840px;padding:0 16px;color:#202124;line-height:1.5}
h1{font-size:22px;margin:0 0 4px}
.sub{color:#5f6368;font-size:13px;margin-bottom:24px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:16px 0 28px}
th,td{text-align:right;padding:6px 10px;border-bottom:1px solid #e8eaed}
th:first-child,td:first-child{text-align:left}
tr.best td{font-weight:600}
.note{font-size:13px;color:#5f6368;border-left:3px solid #dadce0;padding-left:12px}
"""


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def svg_chart(rows: list[dict], width: int = 780, height: int = 300) -> str:
    models = available_models(rows)
    pad_l, pad_r, pad_t, pad_b = 46, 16, 16, 34
    values = [r["y"] for r in rows]
    for key, _, _ in models:
        values += [r[key] for r in rows]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    n = len(rows)

    def x(i: int) -> float:
        return pad_l + i * (width - pad_l - pad_r) / max(n - 1, 1)

    def y(v: float) -> float:
        return height - pad_b - (v - lo) / span * (height - pad_t - pad_b)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'aria-label="Aktual vs prediksi">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
    ]
    for frac in (0, 0.5, 1):
        level = lo + span * frac
        ypos = y(level)
        parts.append(
            f'<line x1="{pad_l}" y1="{ypos:.1f}" x2="{width - pad_r}" y2="{ypos:.1f}" '
            f'stroke="#e8eaed"/>'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{ypos + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#5f6368">{level:.1f}</text>'
        )

    parts.append(
        f'<polyline fill="none" stroke="#202124" stroke-width="2" points="'
        + " ".join(f"{x(i):.1f},{y(r['y']):.1f}" for i, r in enumerate(rows))
        + '"/>'
    )
    for key, label, color in models:
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-dasharray="{"4 3" if key != "pred_feat" else ""}" points="'
            + " ".join(f"{x(i):.1f},{y(r[key]):.1f}" for i, r in enumerate(rows))
            + '"/>'
        )

    for idx, anchor in ((0, "start"), (n // 2, "middle"), (n - 1, "end")):
        parts.append(
            f'<text x="{x(idx):.1f}" y="{height - 12}" text-anchor="{anchor}" '
            f'font-size="11" fill="#5f6368">{rows[idx]["month"]}</text>'
        )

    legend = [("aktual", "#202124")] + [(label, color) for _, label, color in models]
    lx = pad_l
    for label, color in legend:
        parts.append(f'<rect x="{lx}" y="4" width="14" height="3" fill="{color}"/>')
        parts.append(
            f'<text x="{lx + 20}" y="9" font-size="11" fill="#5f6368">{label}</text>'
        )
        lx += 20 + 8 * len(label) + 16

    parts.append("</svg>")
    return "".join(parts)


def metrics_table(rows: list[dict]) -> str:
    models = available_models(rows)
    scores = {key: backtest.metrics(rows, key) for key, _, _ in models}
    best = min(scores, key=lambda k: scores[k]["mae"])
    head = "<tr><th>model</th><th>n</th><th>MAE</th><th>RMSE</th><th>bias</th></tr>"
    body = []
    for key, label, _ in models:
        m = scores[key]
        cls = ' class="best"' if key == best else ""
        body.append(
            f"<tr{cls}><td>{label}</td><td>{m['n']}</td><td>{_fmt(m['mae'])}</td>"
            f"<td>{_fmt(m['rmse'])}</td><td>{m['bias']:+.3f}</td></tr>"
        )
    return f"<table>{head}{''.join(body)}</table>"


def build_report(
    rows: list[dict], target: str, horizon: int, dataset: str, min_train: int
) -> str:
    ci = backtest.mae_diff_ci(rows)
    ci_ar = backtest.mae_diff_ci(rows, base="pred_ar")
    headline_note = ""
    both = backtest.with_predictions(rows, ["pred_feat", "pred_headline"])
    if both:
        ci_hl = backtest.mae_diff_ci(both, base="pred_headline", feat="pred_feat")
        headline_note = (
            f" Vs AR(1)+headline (n={len(both)}): {ci_hl['diff']:+.3f}"
            f" ({ci_hl['lo']:+.3f} s/d {ci_hl['hi']:+.3f})."
        )
    period = f"{rows[0]['month']} s/d {rows[-1]['month']}"
    return f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<title>Laporan nowcast {target}</title><style>{_STYLE}</style></head>
<body>
<h1>Nowcast {target}</h1>
<div class="sub">{len(rows)} bulan uji, {period} · horizon {horizon} ·
minimum {min_train} bulan latih · sumber {dataset}</div>
{metrics_table(rows)}
{svg_chart(rows)}
<p class="note">Selisih MAE fitur harga vs naive: {ci['diff']:+.3f}
(95% CI {ci['lo']:+.3f} s/d {ci['hi']:+.3f}). Vs AR(1): {ci_ar['diff']:+.3f}
({ci_ar['lo']:+.3f} s/d {ci_ar['hi']:+.3f}).{headline_note} CI bootstrap 5.000 resample.
Horizon 0 = nowcast akhir bulan; harga bulan berjalan sudah diketahui, CPI belum rilis.</p>
</body></html>
"""
