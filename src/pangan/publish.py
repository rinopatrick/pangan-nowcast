"""Ekspor dataset bulanan + datasheet untuk publikasi.

Modul ini tidak menyentuh jaringan: masukannya CSV dataset yang sudah ada,
keluarannya satu CSV bersih dan satu datasheet Markdown. Angka di datasheet
dihitung dari data, bukan ditulis tangan.
"""

from __future__ import annotations

import csv
from pathlib import Path

TARGET = "food_mtm"
COMPARATOR = "headline_mtm"

FIELDS = [
    "month",
    "commodity_id",
    "n_obs",
    "mean",
    "last",
    "min",
    "max",
    "std",
    "mom_pct",
    TARGET,
    COMPARATOR,
]

def _blank(value) -> bool:
    return value is None or value == ""

def summary(
    rows: list[dict],
    target: str = TARGET,
    comparator: str = COMPARATOR,
) -> dict:
    months = tuple(sorted({r["month"] for r in rows}))
    commodities = sorted({r["commodity_id"] for r in rows})
    return {
        "n_rows": len(rows),
        "months": months,
        "n_months": len(months),
        "n_commodities": len(commodities),
        "missing_target": sum(1 for r in rows if _blank(r.get(target))),
        "missing_comparator": sum(1 for r in rows if _blank(r.get(comparator))),
        "missing_mom": sum(1 for r in rows if _blank(r.get("mom_pct"))),
        "target": target,
        "comparator": comparator,
    }

def datasheet(info: dict, target: str | None = None) -> str:
    target = target or info["target"]
    first, last = info["months"][0], info["months"][-1]
    return f"""# Datasheet: pangan-nowcast dataset bulanan

## Ringkasan

Panel bulanan harga pangan Indonesia untuk nowcasting inflasi kelompok makanan.
Satu baris = satu komoditas per bulan.

- Baris: {info['n_rows']}
- Bulan: {info['n_months']} ({first} s/d {last})
- Komoditas: {info['n_commodities']}
- Target: `{target}` (inflasi m-to-m kelompok makanan, persen)
- Pembanding: `{info['comparator']}` (inflasi umum m-to-m, persen)

## Sumber

- Harga harian: PIHPS Bank Indonesia, endpoint
  `bi.go.id/hargapangan/WebSite/TabelHarga/GetGridDataKomoditas`. Endpoint ini
  **tidak resmi** dan tidak didokumentasikan, sehingga bisa berubah sewaktu-waktu.
- Target dan pembanding: BPS WebAPI (`var` 1890/2223 untuk makanan, `var` 1 untuk
  inflasi umum). Butuh API key gratis dari https://webapi.bps.go.id/developer/.

## Kolom

| kolom | arti |
|---|---|
| `month` | bulan, format YYYY-MM |
| `commodity_id` | id komoditas PIHPS (`com_*`) |
| `n_obs` | jumlah hari tercatat dalam bulan itu |
| `mean`, `last`, `min`, `max`, `std` | statistik harga harian bulan itu |
| `mom_pct` | perubahan `last` vs bulan sebelumnya, persen |
| `{target}` | inflasi m-to-m kelompok makanan, persen |
| `{info['comparator']}` | inflasi umum m-to-m, persen |

## Kualitas data

- Baris tanpa `mom_pct`: {info['missing_mom']} (bulan pertama tiap komoditas).
- Baris tanpa `{target}`: {info['missing_target']}.
- Baris tanpa `{info['comparator']}`: {info['missing_comparator']}.
- Harga `-` dari sumber disimpan sebagai NULL, bukan nol.
- Akhir pekan dan hari libur tidak memiliki pencatatan.

## Pemakaian yang disarankan

- Backtest rolling-origin dengan target `{target}` dan fitur harga bulan berjalan
  (nowcast akhir bulan), bukan prediksi sebelum bulan berjalan.
- Bandingkan selalu dengan naive dan AR(1); fitur harga baru berguna kalau
  selisih MAE-nya signifikan secara statistik.

## Batasan

- Target disambung dari dua basis IHK (2018=100 dan 2022=100); m-to-m tetap
  sebanding antar basis, tapi level tidak boleh dibandingkan lintas basis.
- Fitur harga masih rata-rata sederhana, belum berbobot konsumsi.
- `{info['comparator']}` dirilis bersamaan dengan target, jadi model yang
  memakainya bukan nowcast yang bisa berjalan sebelum rilis resmi.
- Data komoditas mengikuti cakupan PIHPS, bukan cakupan keranjang IHK BPS.
- Tidak ada jaminan bebas galat dari sumber. Selalu periksa tanggal pembaruan.

## Lisensi dan atribusi

Data harga berasal dari PIHPS Bank Indonesia; target dari BPS. Dataset turunan ini
tidak mengklaim kepemilikan atas data sumber. Cantumkan kedua sumber saat memakai
dataset ini.
"""

def write(
    rows: list[dict],
    out_dir: str | Path,
    target: str = TARGET,
    comparator: str = COMPARATOR,
    stem: str = "pangan_nowcast_monthly",
) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    fields = list(FIELDS)
    for name in (target, comparator):
        if name not in fields:
            fields.append(name)

    csv_path = out / f"{stem}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    info = summary(rows, target=target, comparator=comparator)
    md_path = out / f"{stem}_datasheet.md"
    md_path.write_text(datasheet(info, target=target), encoding="utf-8")
    return csv_path, md_path
