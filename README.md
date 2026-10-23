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

## Target BPS (m-to-m kelompok makanan)

FRED hanya menyediakan YoY. Target m-to-m kelompok makanan diambil dari BPS
WebAPI: `var` 1890 (basis 2018=100, 2020-2023) dan `var` 2223 (basis 2022=100,
2024-2026), baris nasional (`vervar` = `INDONESIA`, `turvar` = `Makanan`).

```bash
export BPS_API_KEY=...

pangan bps-pull --var 1890 --th 120:122 --series food_mtm --turvar Makanan
pangan bps-pull --var 1890 --th 123     --series food_mtm --turvar Makanan
pangan bps-pull --var 2223 --th 123:125 --series food_mtm --turvar Makanan
pangan bps-pull --var 2223 --th 126     --series food_mtm --turvar Makanan
```

- `--th` wajib diisi BPS; maksimal 3 tahun per permintaan. Id periode: 100 = 2000,
  126 = 2026, jadi 120:122 = 2020-2022.
- Hasil: 81 bulan, 2020-01 s/d 2026-09, tanpa bulan hilang.
- Dua basis IHK disambung di 2024. m-to-m adalah persen perubahan bulanan,
  jadi tetap sebanding antar basis; tidak ada penyesuaian level. Ini asumsi yang
  perlu diingat kalau angkanya dipakai untuk klaim jangka panjang.
- Nilai masuk akal: rentang -2,35% s/d +2,30%; YoY implisit 2022 = 5,7%,
  2023 = 6,2%, 2024 = 1,0%, 2025 = 4,9%.

Daftar key gratis di https://webapi.bps.go.id/developer/. Id subjek inflasi = 3.
`bps-pull` mencetak kombinasi `--vervar`/`--turvar` yang tersedia kalau filter
tidak cocok. Adapter sudah diuji terhadap panggilan live.

### Tanpa API key?

WebAPI BPS memang mewajibkan key (gratis). Tapi halaman tabel statistik
menyertakan payload data yang sama di dalam respons Next.js: kirim header
`RSC: 1` ke URL tabel, lalu cari baris yang memuat `"datacontent"`.

Yang sudah diverifikasi pada tabel di atas:

- `var` 2223 = Inflasi Bulanan (M-to-M) (2022=100) Makanan, Minuman dan Tembakau
- `turvar` 1551 = Makanan, Minuman dan Tembakau; 1552 = Makanan;
  1553 = Minuman tidak beralkohol; 1554 = Minuman beralkohol; 1666 = Rokok
- `vervar` 1..150 = kabupaten/kota, **151 = INDONESIA**
- 5.652 titik data, `turtahun` Januari-Desember + Tahunan

Batasan: halaman hanya menyajikan tahun yang sedang dipilih (saat ini 2026).
Tombol ganti tahun memakai aksi internal Next.js yang tidak bisa direplikasi
lewat GET biasa (10 variasi parameter sudah dicoba). Jadi riwayat 2020-2025
praktis butuh API key.

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

Rolling-origin, `--min-train 30`, tiap prediksi hanya memakai data sebelum bulan uji.
Nowcast, bukan ramalan: harga bulan t diketahui pada akhir bulan t, CPI rilis awal t+1.

| target | model | n | MAE | RMSE |
|---|---|---|---|---|
| `cpi_yoy` (inflasi umum YoY) | naive | 31 | 0.361 | 0.465 |
| `cpi_yoy` | AR(1) | 31 | 0.398 | 0.506 |
| `cpi_yoy` | AR(1)+harga | 31 | 0.398 | 0.511 |
| `food_mtm` (makanan m-to-m) | naive | 48 | 0.981 | 1.288 |
| `food_mtm` | AR(1) | 48 | 0.795 | 0.989 |
| `food_mtm` | AR(1)+harga | 48 | 0.714 | 0.880 |

Selisih MAE fitur harga, bootstrap 5.000 resample:

- `food_mtm` vs naive: **-0.268** [-0.436, -0.107]
- `food_mtm` vs AR(1): **-0.082** [-0.147, -0.017]
- `cpi_yoy` vs AR(1): -0.001 [-0.019, +0.017]

Kesimpulan: harga pangan harian menambah akurasi untuk nowcast **inflasi makanan
m-to-m**, dan selisihnya tetap signifikan setelah inersia AR(1) dikontrol. Untuk
inflasi umum YoY, fitur harga tidak menambah apa pun.

Batasan: 48 bulan uji, target disambung antar dua basis IHK, fitur masih rata-rata
sederhana tanpa bobot konsumsi, dan satu kali spesifikasi (tanpa tuning). Fitur
memakai harga sepanjang bulan, jadi ini nowcast akhir bulan (CPI belum rilis),
bukan prediksi sebelum bulan berjalan.

## Selanjutnya

1. Fitur indeks harga pangan berbobot konsumsi, bukan rata-rata sederhana.
2. Uji horizon 1 bulan (forecast, bukan nowcast).
3. Bandingkan target kelompok lain (minuman, rokok) sebagai kontrol negatif.
4. Dashboard + laporan.

## Test

```bash
pytest
```
