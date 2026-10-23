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

## Sumber data

Endpoint `bi.go.id/hargapangan/WebSite/TabelHarga/GetGridDataKomoditas`.
Tidak resmi, tidak didokumentasikan, bisa berubah tanpa pemberitahuan.

- `com_*` = komoditas, `cat_*` = kategori. Ingest default hanya `com_*`.
- `price_type_id`: 1 pasar tradisional, 2 modern, 3 pedagang besar, 4 produsen.
- `province_id=0` mengembalikan baris agregat `Semua Provinsi`; kosong = semua provinsi.
- Tanggal tanpa pencatatan (akhir pekan, libur) tidak muncul sebagai kolom.
- Nilai `-` disimpan sebagai `NULL`.

Hormati sumbernya: `--sleep 1` default, jangan jalankan paralel.

## Selanjutnya

1. Join dengan inflasi bulanan BPS (kelompok makanan).
2. Agregasi harian -> bulanan: rata-rata, akhir bulan, volatilitas.
3. Backtest rolling-origin, baseline AR vs AR + fitur harga.
4. Dashboard + laporan.

## Test

```bash
pytest
```
