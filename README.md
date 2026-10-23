# pangan-nowcast

Harga pangan harian Indonesia (PIHPS, Bank Indonesia) dirapikan jadi SQLite,
sebagai bahan nowcasting inflasi pangan.

Status: tahap 1 (ingest). Belum ada model, belum ada backtest.

## Pasang

```bash
pip install -e ".[dev]"
```

## Pakai

```bash
# daftar komoditas, provinsi, jenis pasar
pangan refs

# satu komoditas, satu tahun
pangan ingest --start 2024-01-01 --end 2024-12-31 --commodity com_13

# semua komoditas, agregat nasional saja (cepat)
pangan ingest --start 2020-01-01 --end 2026-10-23 --province 0

# semua komoditas, semua provinsi (lambat: ~40 detik per komoditas)
pangan ingest --start 2020-01-01 --end 2026-10-23
```

Hasil: `data/pangan.db`, tabel `price(commodity_id, price_type_id, province, date, value)`.
Baris `province = 'Semua Provinsi'` adalah agregat nasional dari sumber.

```sql
SELECT date, value FROM price
WHERE commodity_id = 'com_13' AND province = 'Semua Provinsi'
ORDER BY date;
```

## Dataset untuk model

```bash
pangan cpi                        # unduh inflasi bulanan (FRED) -> tabel macro
pangan dataset --out data/dataset.csv
```

`dataset.csv` satu baris per komoditas per bulan:

| kolom | arti |
|---|---|
| `month` | YYYY-MM |
| `commodity_id` | `com_*` |
| `n_obs` | jumlah hari tercatat di bulan itu |
| `mean`, `last`, `min`, `max`, `std` | statistik harga harian bulan itu |
| `mom_pct` | perubahan `last` vs bulan sebelumnya, persen |
| `cpi_yoy` | inflasi umum nasional year-on-year (persen) |

## Sumber data

Endpoint `bi.go.id/hargapangan/WebSite/TabelHarga/GetGridDataKomoditas`.
Tidak resmi, tidak didokumentasikan, bisa berubah tanpa pemberitahuan.

- `com_*` = komoditas, `cat_*` = kategori. Ingest default hanya `com_*`.
- `price_type_id`: 1 pasar tradisional, 2 modern, 3 pedagang besar, 4 produsen.
- `province_id=0` mengembalikan baris agregat `Semua Provinsi`; kosong = semua provinsi.
- Tanggal tanpa pencatatan (akhir pekan, libur) tidak muncul sebagai kolom.
- Nilai `-` disimpan sebagai `NULL`.
- Rentang panjang dipecah per tahun; tiap permintaan ~5 detik.

Inflasi bulanan diambil dari FRED `CPALTT01IDM659N` (OECD MEI), tanpa API key.
Batasan: itu inflasi umum **year-on-year**, bukan m-to-m dan bukan kelompok makanan,
dan mengikuti jadwal OECD sehingga sekitar 1-1,5 tahun terakhir bisa tertinggal.
Nilai 2024-01 = 2,57 cocok dengan inflasi YoY resmi BPS.
Untuk m-to-m per kelompok, pakai BPS WebAPI (butuh API key gratis).

Hormati sumbernya: `--sleep 1` default, jangan jalankan paralel.

## Selanjutnya

1. Backtest rolling-origin: baseline AR vs AR + fitur harga (2020-2025).
2. Ganti target ke inflasi kelompok makanan begitu akses BPS tersedia.
3. Dashboard + laporan.

## Test

```bash
pytest
```
