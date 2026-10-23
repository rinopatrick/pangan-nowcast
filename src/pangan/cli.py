"""CLI: pangan refs | ingest | cpi | bps-vars | bps-pull | dataset | backtest."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from . import backtest, bps, features, macro, pihps, publish, report, store


def _cmd_refs(db: str) -> int:
    con = store.connect(db)
    store.init(con)
    n = store.save_refs(con, pihps.commodities(), pihps.provinces(), pihps.price_types())
    print(f"refs tersimpan: {n} baris")
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    con = store.connect(args.db)
    store.init(con)
    refs = pihps.commodities()
    if not con.execute("SELECT 1 FROM commodity LIMIT 1").fetchone():
        store.save_refs(con, refs, pihps.provinces(), pihps.price_types())

    if args.commodity:
        targets = args.commodity
    else:
        targets = [c["id"] for c in refs if c["id"].startswith("com_")]

    total = 0
    for commodity_id in targets:
        for chunk_start, chunk_end in pihps.year_chunks(args.start, args.end):
            payload = pihps.grid(
                commodity_id, chunk_start, chunk_end, args.price_type, args.province
            )
            rows = pihps.melt(payload, commodity_id, args.price_type)
            total += store.save_prices(con, rows)
            print(f"{commodity_id} {chunk_start[:4]}: +{len(rows)}", flush=True)
            time.sleep(args.sleep)
    print(f"selesai: {total} baris", flush=True)
    return 0


def _cmd_cpi(args: argparse.Namespace) -> int:
    con = store.connect(args.db)
    store.init(con)
    rows = macro.fetch()
    n = macro.save(con, rows)
    print(f"cpi: {n} bulan, terakhir {rows[-1][1] if rows else '-'}")
    return 0


def _list_items(payload: dict) -> list[dict]:
    data = payload.get("data") or {}
    if isinstance(data, dict):
        return data.get("1") or []
    return data[1] if len(data) > 1 else []


def _cmd_bps_vars(args: argparse.Namespace) -> int:
    payload = bps.list_vars(subject=args.subject, page=args.page)
    items = _list_items(payload)
    if not items:
        print("tidak ada variabel pada halaman ini", file=sys.stderr)
        return 1
    for item in items:
        print(f"{item.get('var_id')}\t{item.get('title')}\t[{item.get('unit')}]")
    return 0


def _cmd_bps_pull(args: argparse.Namespace) -> int:
    con = store.connect(args.db)
    store.init(con)
    payload = bps.fetch_data(args.var, th=args.th)
    rows = bps.monthly_series(payload, vervar=args.vervar, turvar=args.turvar)
    if not rows:
        combos = sorted({(r["vervar"], r["turvar"]) for r in bps.parse_rows(payload)})
        print("tidak ada seri bulanan yang cocok. Kombinasi tersedia:", file=sys.stderr)
        for vervar, turvar in combos[:20]:
            print(f"  --vervar {vervar!r} --turvar {turvar!r}", file=sys.stderr)
        return 1
    saved = macro.save(con, [(args.series, r["month"], r["value"]) for r in rows])
    print(f"{args.series}: {saved} bulan, {rows[0]['month']} .. {rows[-1]['month']}")
    return 0


def _cmd_dataset(args: argparse.Namespace) -> int:
    con = store.connect(args.db)
    store.init(con)
    cur = con.execute(
        """
        SELECT commodity_id, date,
               CASE WHEN SUM(province = 'Semua Provinsi') > 0
                    THEN MAX(CASE WHEN province = 'Semua Provinsi' THEN value END)
                    ELSE AVG(value) END
        FROM price
        GROUP BY commodity_id, date
        ORDER BY date
        """
    )
    prices = cur.fetchall()
    if not prices:
        print("tabel price kosong; jalankan 'pangan ingest' dulu", file=sys.stderr)
        return 1
    target = macro.load(con, args.target_series)
    if not target:
        print(f"seri '{args.target_series}' kosong di tabel macro", file=sys.stderr)
        return 1
    extras = {}
    for spec in args.extra or []:
        if "=" not in spec:
            print(f"--extra harus NAME=SERIES, bukan {spec!r}", file=sys.stderr)
            return 1
        name, series = spec.split("=", 1)
        values = macro.load(con, series)
        if not values:
            print(f"seri '{series}' kosong di tabel macro", file=sys.stderr)
            return 1
        extras[name.strip()] = values
    rows = features.build_dataset(prices, target, args.target_name, extras=extras)
    fields = ["month", "commodity_id", *features.MONTH_FIELDS, args.target_name, *extras]
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"dataset: {len(rows)} baris -> {args.out}")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    panel = backtest.load_dataset(args.dataset, target=args.target, horizon=args.horizon)
    rows = backtest.rolling(panel, min_train=args.min_train)
    if not rows:
        print("data tidak cukup untuk backtest", file=sys.stderr)
        return 1
    print(f"target={args.target} horizon={args.horizon} uji={rows[0]['month']}..{rows[-1]['month']}")
    for label, key in [
        ("naive", "pred_base"),
        ("AR(1)", "pred_ar"),
        ("AR(1)+harga", "pred_feat"),
        ("AR(1)+headline", "pred_headline"),
    ]:
        subset = backtest.with_predictions(rows, [key])
        if not subset:
            continue
        m = backtest.metrics(subset, key)
        print(
            f"{label:14s} n={m['n']:3d}  MAE={m['mae']:.3f}  "
            f"RMSE={m['rmse']:.3f}  bias={m['bias']:+.3f}"
        )
    ci = backtest.mae_diff_ci(rows)
    print(
        f"selisih MAE (harga - naive): {ci['diff']:+.3f}  "
        f"95% CI [{ci['lo']:+.3f}, {ci['hi']:+.3f}]"
    )
    ci_ar = backtest.mae_diff_ci(rows, base="pred_ar")
    print(
        f"selisih MAE (harga - AR):    {ci_ar['diff']:+.3f}  "
        f"95% CI [{ci_ar['lo']:+.3f}, {ci_ar['hi']:+.3f}]"
    )
    both = backtest.with_predictions(rows, ["pred_feat", "pred_headline"])
    if both:
        ci_hl = backtest.mae_diff_ci(both, base="pred_headline", feat="pred_feat")
        print(
            f"selisih MAE (harga - headline, n={len(both)}): {ci_hl['diff']:+.3f}  "
            f"95% CI [{ci_hl['lo']:+.3f}, {ci_hl['hi']:+.3f}]"
        )
    fields = ["month", "origin", "y", "pred_base", "pred_ar", "pred_feat", "pred_headline", "n_train"]
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"prediksi: {len(rows)} bulan -> {args.out}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    panel = backtest.load_dataset(args.dataset, target=args.target, horizon=args.horizon)
    rows = backtest.rolling(panel, min_train=args.min_train)
    if not rows:
        print("data tidak cukup untuk laporan", file=sys.stderr)
        return 1
    html = report.build_report(
        rows, args.target, args.horizon, args.dataset, args.min_train
    )
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"laporan: {len(rows)} bulan -> {args.out}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    with open(args.dataset, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print(f"dataset kosong: {args.dataset}", file=sys.stderr)
        return 1
    csv_path, md_path = publish.write(
        rows,
        args.out,
        target=args.target,
        comparator=args.comparator,
    )
    info = publish.summary(rows, target=args.target, comparator=args.comparator)
    print(
        f"export: {info['n_rows']} baris, {info['n_months']} bulan, "
        f"{info['n_commodities']} komoditas -> {csv_path}"
    )
    print(f"datasheet: {md_path}")
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pangan", description="Harga pangan harian PIHPS -> SQLite")
    parser.add_argument("--db", default="data/pangan.db")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("refs", help="simpan daftar komoditas/provinsi/jenis pasar")

    ingest = sub.add_parser("ingest", help="unduh harga harian untuk satu rentang tanggal")
    ingest.add_argument("--start", required=True, help="YYYY-MM-DD")
    ingest.add_argument("--end", required=True, help="YYYY-MM-DD")
    ingest.add_argument(
        "--price-type", type=int, default=1, help="1 tradisional, 2 modern, 3 grosir, 4 produsen"
    )
    ingest.add_argument(
        "--province",
        default="",
        help="kosong = semua provinsi (~40 dtk/komoditas), 0 = agregat nasional saja (~4 dtk)",
    )
    ingest.add_argument("--commodity", action="append", help="mis. com_13; default semua com_*")
    ingest.add_argument("--sleep", type=float, default=1.0, help="jeda antar permintaan (detik)")

    sub.add_parser("cpi", help="unduh inflasi YoY bulanan (FRED) ke SQLite")

    bps_vars = sub.add_parser("bps-vars", help="daftar variabel BPS (butuh BPS_API_KEY)")
    bps_vars.add_argument("--subject", type=int, help="id subjek, mis. 22 = inflasi")
    bps_vars.add_argument("--page", type=int, default=1)

    bps_pull = sub.add_parser("bps-pull", help="unduh satu variabel BPS -> tabel macro")
    bps_pull.add_argument("--var", type=int, required=True)
    bps_pull.add_argument("--th", required=True, help="periode BPS: 126, atau rentang 120:126")
    bps_pull.add_argument("--series", required=True, help="nama seri di tabel macro, mis. food_mtm")
    bps_pull.add_argument("--vervar", default="INDONESIA")
    bps_pull.add_argument("--turvar", help="label turvar, mis. 'Makanan, Minuman dan Tembakau'")

    dataset = sub.add_parser("dataset", help="fitur bulanan + target -> CSV")
    dataset.add_argument("--out", default="data/dataset.csv")
    dataset.add_argument("--target-series", default=macro.SERIES, help="seri di tabel macro")
    dataset.add_argument("--target-name", default="cpi_yoy", help="nama kolom target di CSV")
    dataset.add_argument(
        "--extra",
        action="append",
        metavar="NAME=SERIES",
        help="kolom tambahan dari tabel macro, mis. headline_mtm=bps_headline_mtm",
    )

    bt = sub.add_parser("backtest", help="rolling-origin: naive vs AR(1)+fitur harga")
    bt.add_argument("--dataset", default="data/dataset.csv")
    bt.add_argument("--target", default="cpi_yoy", help="nama kolom target di dataset")
    bt.add_argument("--horizon", type=int, default=0, choices=[0, 1], help="0 = nowcast, 1 = forecast")
    bt.add_argument("--min-train", type=int, default=30)
    bt.add_argument("--out", default="data/backtest.csv")

    rp = sub.add_parser("report", help="laporan HTML mandiri (tabel + grafik)")
    rp.add_argument("--dataset", default="data/dataset_food.csv")
    rp.add_argument("--target", default="food_mtm")
    rp.add_argument("--horizon", type=int, default=0, choices=[0, 1])
    rp.add_argument("--min-train", type=int, default=30)
    rp.add_argument("--out", default="report.html")

    ex = sub.add_parser("export", help="dataset bulanan + datasheet untuk publikasi")
    ex.add_argument("--dataset", default="data/dataset_food.csv")
    ex.add_argument("--out", default="data/publish")
    ex.add_argument("--target", default=publish.TARGET)
    ex.add_argument("--comparator", default=publish.COMPARATOR)

    args = parser.parse_args(argv)
    try:
        if args.cmd == "refs":
            return _cmd_refs(args.db)
        if args.cmd == "cpi":
            return _cmd_cpi(args)
        if args.cmd == "bps-vars":
            return _cmd_bps_vars(args)
        if args.cmd == "bps-pull":
            return _cmd_bps_pull(args)
        if args.cmd == "dataset":
            return _cmd_dataset(args)
        if args.cmd == "backtest":
            return _cmd_backtest(args)
        if args.cmd == "report":
            return _cmd_report(args)
        if args.cmd == "export":
            return _cmd_export(args)
        return _cmd_ingest(args)
    except (bps.BpsError, pihps.PihpsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
