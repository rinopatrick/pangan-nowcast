"""CLI: pangan refs | pangan ingest --start ... --end ..."""

from __future__ import annotations

import argparse
import csv
import sys
import time

from . import backtest, features, macro, pihps, store


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
    rows = features.build_dataset(prices, macro.load(con))
    fields = ["month", "commodity_id", *features.MONTH_FIELDS, "cpi_yoy"]
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"dataset: {len(rows)} baris -> {args.out}")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    panel = backtest.load_dataset(args.dataset)
    rows = backtest.rolling(panel, min_train=args.min_train)
    if not rows:
        print("data tidak cukup untuk backtest", file=sys.stderr)
        return 1
    for label, key in [("naive", "pred_base"), ("AR(1)+harga", "pred_feat")]:
        m = backtest.metrics(rows, key)
        print(f"{label:12s} n={m['n']:3d}  MAE={m['mae']:.3f}  RMSE={m['rmse']:.3f}  bias={m['bias']:+.3f}")
    ci = backtest.mae_diff_ci(rows)
    print(f"selisih MAE (harga - naive): {ci['diff']:+.3f}  95% CI [{ci['lo']:+.3f}, {ci['hi']:+.3f}]")
    fields = ["month", "y", "pred_base", "pred_feat", "n_train"]
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"prediksi: {len(rows)} bulan -> {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pangan", description="Harga pangan harian PIHPS -> SQLite")
    parser.add_argument("--db", default="data/pangan.db")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("refs", help="simpan daftar komoditas/provinsi/jenis pasar")

    ingest = sub.add_parser("ingest", help="unduh harga harian untuk satu rentang tanggal")
    ingest.add_argument("--start", required=True, help="YYYY-MM-DD")
    ingest.add_argument("--end", required=True, help="YYYY-MM-DD")
    ingest.add_argument("--price-type", type=int, default=1, help="1 tradisional, 2 modern, 3 grosir, 4 produsen")
    ingest.add_argument(
        "--province",
        default="",
        help="kosong = semua provinsi (~40 dtk/komoditas), 0 = agregat nasional saja (~4 dtk)",
    )
    ingest.add_argument("--commodity", action="append", help="mis. com_13; default semua com_*")
    ingest.add_argument("--sleep", type=float, default=1.0, help="jeda antar permintaan (detik)")

    sub.add_parser("cpi", help="unduh inflasi bulanan (FRED) ke SQLite")

    dataset = sub.add_parser("dataset", help="fitur bulanan + inflasi -> CSV")
    dataset.add_argument("--out", default="data/dataset.csv")

    bt = sub.add_parser("backtest", help="rolling-origin: AR(1) vs AR(1)+fitur harga")
    bt.add_argument("--dataset", default="data/dataset.csv")
    bt.add_argument("--min-train", type=int, default=30)
    bt.add_argument("--out", default="data/backtest.csv")

    args = parser.parse_args(argv)
    if args.cmd == "refs":
        return _cmd_refs(args.db)
    if args.cmd == "cpi":
        return _cmd_cpi(args)
    if args.cmd == "dataset":
        return _cmd_dataset(args)
    if args.cmd == "backtest":
        return _cmd_backtest(args)
    return _cmd_ingest(args)


if __name__ == "__main__":
    sys.exit(main())
