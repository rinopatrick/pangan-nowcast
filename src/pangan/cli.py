"""CLI: pangan refs | pangan ingest --start ... --end ..."""

from __future__ import annotations

import argparse
import sys
import time

from . import pihps, store


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
        payload = pihps.grid(commodity_id, args.start, args.end, args.price_type, args.province)
        rows = pihps.melt(payload, commodity_id, args.price_type)
        total += store.save_prices(con, rows)
        print(f"{commodity_id}: {len(rows)} baris")
        time.sleep(args.sleep)
    print(f"selesai: {total} baris")
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

    args = parser.parse_args(argv)
    if args.cmd == "refs":
        return _cmd_refs(args.db)
    return _cmd_ingest(args)


if __name__ == "__main__":
    sys.exit(main())
