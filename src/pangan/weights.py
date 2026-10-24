"""Bobot konsumsi IHK 2022=100 untuk komoditas PIHPS.

Sumber angka: BPS, "Diagram Timbang Indeks Harga Konsumen Hasil Survei Biaya
Hidup 2022", Katalog 7102024, Tabel 1.1 halaman 3-38 (nasional).
Kolom yang dipakai adalah "Persentase Nilai Konsumsi Terhadap Total" (persen
dari seluruh keranjang IHK nasional), bukan persen terhadap kelompok.

10 kategori IHK di bawah ini adalah satu-satunya yang bisa dipetakan ke 21
komoditas PIHPS. Totalnya 9.6964% dari keranjang IHK, atau 34.63% dari kelompok
Makanan (27.9999%).
"""

from __future__ import annotations

# kategori IHK -> (bobot persen dari total IHK, komoditas PIHPS)
CATEGORIES: list[tuple[str, float, list[str]]] = [
    ("BERAS", 3.4260, ["com_1", "com_2", "com_3", "com_4", "com_5", "com_6"]),
    ("DAGING AYAM RAS", 1.5843, ["com_7"]),
    ("DAGING SAPI", 0.4926, ["com_8", "com_9"]),
    ("TELUR AYAM RAS", 0.9333, ["com_10"]),
    ("BAWANG MERAH", 0.5098, ["com_11"]),
    ("BAWANG PUTIH", 0.3173, ["com_12"]),
    ("CABAI MERAH", 0.4485, ["com_13", "com_14"]),
    ("CABAI RAWIT", 0.3395, ["com_15", "com_16"]),
    ("MINYAK GORENG", 1.3175, ["com_17", "com_18", "com_19"]),
    ("GULA PASIR", 0.3276, ["com_20", "com_21"]),
]

COVERAGE = sum(weight for _, weight, _ in CATEGORIES)
FOOD_GROUP = 27.9999

def weighted_mom(monthly: dict[tuple[str, str], dict]) -> dict[str, float]:
    """Rata-rata m-to-m per bulan, dibobot IHK.

    `monthly` berbentuk {(commodity_id, "YYYY-MM"): {"mom_pct": ...}}.
    Beberapa komoditas PIHPS dalam satu kategori dirata-ratakan lebih dulu,
    lalu kategori dibobot. Bobot dinormalisasi ulang hanya atas kategori yang
    punya data bulan itu, supaya bulan dengan data tidak lengkap tidak bias ke nol.
    """
    members = {cid: (name, weight) for name, weight, ids in CATEGORIES for cid in ids}

    per_month: dict[str, dict[str, list[float]]] = {}
    for (commodity_id, month), feats in monthly.items():
        entry = members.get(commodity_id)
        if entry is None:
            continue
        value = feats.get("mom_pct")
        if value is None:
            continue
        name, _ = entry
        per_month.setdefault(month, {}).setdefault(name, []).append(value)

    weights_by_name = {name: weight for name, weight, _ in CATEGORIES}

    out: dict[str, float] = {}
    for month, groups in per_month.items():
        total_weight = 0.0
        total = 0.0
        for name, values in groups.items():
            weight = weights_by_name[name]
            total += weight * (sum(values) / len(values))
            total_weight += weight
        if total_weight:
            out[month] = total / total_weight
    return out
