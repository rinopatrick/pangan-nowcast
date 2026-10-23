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

## Hasil backtest

`pangan backtest --min-train 30` — rolling-origin, 31 bulan uji (2022-10 s/d 2025-04).
Tiap prediksi hanya memakai data sebelum bulan uji.

```
naive        n= 31  MAE=0.361  RMSE=0.465  bias=-0.129
AR(1)+harga  n= 31  MAE=0.398  RMSE=0.511  bias=-0.182
selisih MAE (harga - naive): +0.036  95% CI [-0.005, +0.086]
```

Kesimpulan: fitur harga pangan **tidak** memperbaiki nowcast inflasi umum YoY.
Selisih tidak signifikan (CI memuat 0) dan arahnya lebih buruk dari baseline.
Dugaan penyebab: target YoY halus dan didominasi inersia, sementara fitur hanya
momentum satu bulan dari rata-rata komoditas tanpa bobot.

Tidak ada varian fitur/model yang dicoba setelah melihat hasil ini, supaya tidak
terjadi p-hacking. Kandidat berikutnya harus ditetapkan sebelum dijalankan:
target m-to-m atau kelompok makanan (butuh BPS), indeks harga berbobot, dan
perbandingan horizon 0 vs 1 bulan.

## Selanjutnya

1. Target m-to-m / kelompok makanan via BPS WebAPI (API key gratis).
2. Fitur indeks harga pangan berbobot konsumsi, bukan rata-rata sederhana.
3. Uji horizon 1 bulan (forecast, bukan nowcast).
4. Dashboard + laporan.

## Test

```bash
pytest
```
