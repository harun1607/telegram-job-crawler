import os
import re
import csv
import asyncio
import tempfile
import pytesseract

# Konfigurasi lokasi executable Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

from datetime import datetime, date
from zoneinfo import ZoneInfo

from PIL import Image
from dotenv import load_dotenv
from telethon import TelegramClient


# ============================================================
# 1. KONFIGURASI PROJECT
# ============================================================

# Membaca konfigurasi API dari file .env.
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

if not API_ID or not API_HASH:
    raise ValueError(
        "API_ID atau API_HASH belum diisi di file .env"
    )

API_ID = int(API_ID)

# Zona waktu Indonesia bagian barat.
TIMEZONE = ZoneInfo("Asia/Jakarta")

# Daftar channel Telegram publik yang akan diambil datanya.
# Gunakan username channel, bukan URL lengkap.
CHANNELS = [
    "ikjofficial",
    #"infoinlokerpabrik",
    #"lowongankerjatangsel",
    #"lokertgrterbaru",
    #"lokerkucom",
]

# Batas jumlah pesan yang diambil dari setiap channel.
LIMIT_MESSAGES = 20

# Folder dan nama file hasil crawling.
OUTPUT_DIR = "output"

ACTIVE_FILE = os.path.join(
    OUTPUT_DIR,
    "lowongan_aktif.csv"
)

REVIEW_FILE = os.path.join(
    OUTPUT_DIR,
    "lowongan_review.csv"
)

CLOSED_FILE = os.path.join(
    OUTPUT_DIR,
    "lowongan_tutup.csv"
)


# ============================================================
# 2. DAFTAR KEYWORD BLUE COLLAR
# ============================================================

# Keyword digunakan untuk menyaring postingan yang relevan.
# Daftar ini dapat ditambah sesuai kebutuhan perusahaan.

BLUECOLLAR_KEYWORDS = [
    "operator produksi",
    "operator",
    "helper",
    "helper gudang",
    "warehouse",
    "gudang",
    "packing",
    "packaging",
    "picker",
    "packer",
    "kurir",
    "delivery",
    "driver",
    "supir",
    "security",
    "satpam",
    "cleaning service",
    "cleaner",
    "teknisi",
    "mekanik",
    "maintenance",
    "crew",
    "barista",
    "waiter",
    "waitress",
    "staff produksi",
    "pekerja pabrik",
    "bongkar muat",
    "konstruksi",
    "buruh",
    "penjahit",
    "koki",
    "steward",
    "sales lapangan",
]

# Keyword ini menjadi bukti bahwa lowongan sudah ditutup.
CLOSED_KEYWORDS = [
    "lowongan sudah ditutup",
    "lowongan telah ditutup",
    "rekrutmen telah ditutup",
    "rekrutmen sudah ditutup",
    "recruitment closed",
    "closed recruitment",
    "position closed",
    "posisi sudah terisi",
    "posisi telah terisi",
    "kuota terpenuhi",
    "tidak menerima lamaran",
    "sudah tidak menerima lamaran",
    "lowongan sudah tidak tersedia",
]

# Keyword ini menjadi bukti eksplisit bahwa lamaran masih dibuka.
OPEN_KEYWORDS = [
    "lowongan masih dibuka",
    "lamaran masih dibuka",
    "pendaftaran masih dibuka",
    "open recruitment",
    "open vacancy",
    "hiring now",
    "apply now",
    "masih menerima lamaran",
    "pendaftaran dibuka",
    "kirim lamaran sekarang",
]


# ============================================================
# 3. FUNGSI PEMBERSIHAN TEKS
# ============================================================

def clean_text(text):
    """
    Membersihkan teks postingan Telegram.

    Fungsi ini dibuat agar hasil crawling lebih konsisten.
    Misalnya, menghapus spasi berlebih dan baris kosong
    yang terlalu banyak.

    Input:
        text = teks asli dari Telegram.

    Output:
        Teks yang sudah dibersihkan.
    """

    if not text:
        return ""

    text = text.replace("\r", "")

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# 4. FUNGSI OCR GAMBAR
# ============================================================


async def extract_message_text(message):
    """
    Mengambil teks dari pesan Telegram.

    Fungsi ini menangani tiga kondisi:
    1. Pesan hanya berisi teks.
    2. Pesan berisi gambar tanpa caption.
    3. Pesan berisi gambar sekaligus caption.

    Jika terdapat gambar, program mengunduh gambar
    sementara, menjalankan OCR, lalu menggabungkan
    hasil OCR dengan caption.

    Hasil akhirnya berupa teks yang bisa diproses
    oleh fungsi filtering dan ekstraksi sebelumnya.
    """

    # Ambil caption atau teks asli Telegram.
    caption = message.text or ""

    # Periksa apakah pesan memiliki gambar.
    is_image = (
        message.photo is not None
        or (
            message.document is not None
            and (message.document.mime_type or "").startswith(
                "image/"
            )
        )
    )

    # Jika bukan gambar, gunakan teks asli.
    if not is_image:
        return clean_text(caption)

    try:

        # Buat folder sementara untuk menyimpan gambar.
        with tempfile.TemporaryDirectory() as temp_dir:

            # Download gambar dari Telegram.
            image_path = await message.download_media(
                file=temp_dir
            )

            if not image_path:
                return clean_text(caption)

            # Buka gambar menggunakan Pillow.
            with Image.open(image_path) as image:

                # Pastikan gambar menggunakan format RGB.
                image = image.convert("RGB")

                # Jalankan OCR untuk membaca teks gambar.
                extracted_text = pytesseract.image_to_string(
                    image,
                    lang="ind+eng",
                    config="--psm 6"
                )

            # Gabungkan caption dan teks hasil OCR.
            combined_text = "\n".join(
                part for part in [
                    caption,
                    extracted_text
                ]
                if part.strip()
            )

            return clean_text(combined_text)

    except Exception as error:

        print(f"[OCR ERROR] {error}")

        # Jika OCR gagal, caption tetap bisa digunakan.
        return clean_text(caption)


# # ============================================================
# 5. FUNGSI FILTER BLUE COLLAR
# ============================================================

def is_bluecollar_job(text):
    """
    Memeriksa apakah postingan mengandung keyword
    pekerjaan blue collar.

    Fungsi ini mencegah crawler mengambil seluruh
    postingan channel tanpa seleksi.

    Output:
        True  = ditemukan keyword blue collar.
        False = tidak ditemukan keyword.
    """

    text_lower = text.lower()

    for keyword in BLUECOLLAR_KEYWORDS:

        if keyword in text_lower:
            return True

    return False


# ============================================================
# 6. FUNGSI KATEGORISASI PEKERJAAN
# ============================================================

def detect_job_category(text):
    """
    Menentukan kategori pekerjaan berdasarkan keyword.

    Contoh:
        'Operator Produksi' -> Operator Produksi
        'Helper Gudang'     -> Gudang
        'Kurir Motor'       -> Transportasi

    Jika tidak ditemukan kategori spesifik,
    hasilnya menjadi Blue Collar Lainnya.
    """

    categories = {
        "Operator Produksi": [
            "operator produksi",
            "staff produksi",
            "pekerja pabrik",
            "manufaktur",
        ],

        "Gudang": [
            "helper gudang",
            "warehouse",
            "gudang",
            "packing",
            "packaging",
            "picker",
            "packer",
            "bongkar muat",
        ],

        "Transportasi": [
            "kurir",
            "delivery",
            "driver",
            "supir",
        ],

        "Keamanan": [
            "security",
            "satpam",
        ],

        "Kebersihan": [
            "cleaning service",
            "cleaner",
        ],

        "Teknisi": [
            "teknisi",
            "mekanik",
            "maintenance",
        ],

        "Food & Beverage": [
            "barista",
            "waiter",
            "waitress",
            "koki",
            "steward",
        ],

        "Sales Lapangan": [
            "sales lapangan",
        ],
    }

    text_lower = text.lower()

    for category, keywords in categories.items():

        for keyword in keywords:

            if keyword in text_lower:
                return category

    return "Blue Collar Lainnya"


# ============================================================
# 7. FUNGSI EKSTRAKSI JUDUL PEKERJAAN
# ============================================================

def extract_job_title(text):
    """
    Mengambil kemungkinan judul pekerjaan.

    Menghapus prefix nomor urut dan karakter dekoratif
    sebelum mengembalikan judul.

    Contoh:
        1. Operator Produksi -> Operator Produksi
        - Kurir Motor       -> Kurir Motor
        # Driver            -> Driver
    """

    lines = text.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # Hapus nomor urut di awal baris.
        line = re.sub(
            r"^\d+[.)]\s*",
            "",
            line
        )

        # Hapus karakter dekoratif.
        line = re.sub(
            r"^[#\-*•\s]+",
            "",
            line
        )

        line_lower = line.lower()

        if any(
            keyword in line_lower
            for keyword in BLUECOLLAR_KEYWORDS
        ):

            return line[:200]

    # Fallback jika tidak ada keyword pekerjaan.
    for line in lines:

        line = line.strip()

        if line:

            line = re.sub(
                r"^\d+[.)]\s*",
                "",
                line
            )

            line = re.sub(
                r"^[#\-*•\s]+",
                "",
                line
            )

            return line[:200]

    return "Tidak diketahui"


# ============================================================
# 8. FUNGSI EKSTRAKSI NAMA PERUSAHAAN
# ============================================================

def extract_company(text):
    """
    Mendeteksi nama perusahaan berdasarkan pola PT atau CV.

    Regex digunakan untuk mencari teks yang mengikuti
    pola nama perusahaan.

    Jika nama perusahaan tidak ditemukan,
    hasilnya menjadi Tidak diketahui.

    Catatan:
        Nama yang berhasil ditemukan perlu diperiksa,
        karena regex belum memahami batas nama perusahaan
        secara sempurna.
    """

    patterns = [
        r"\b(?:PT|CV)\.?\s+[A-Z][A-Za-z0-9&.,\- ]{2,80}",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            company = match.group(0)

            return company.strip(" .,;:-")

    return "Tidak diketahui"


# ============================================================
# 9. FUNGSI EKSTRAKSI LOKASI
# ============================================================

def extract_location(text):
    """
    Mendeteksi lokasi pekerjaan berdasarkan daftar wilayah.

    Daftar wilayah dapat ditambah sesuai kebutuhan,
    terutama kawasan industri dan area operasional.

    Fungsi ini mengembalikan seluruh wilayah yang ditemukan.
    """

    locations = [
        "Jakarta Selatan",
        "Jakarta Barat",
        "Jakarta Timur",
        "Jakarta Utara",
        "Jakarta Pusat",
        "Tangerang Selatan",
        "Tangerang",
        "Cikarang",
        "Bekasi",
        "Karawang",
        "Bogor",
        "Depok",
        "Bandung",
        "Semarang",
        "Surabaya",
        "Yogyakarta",
        "Serang",
        "Purwakarta",
        "Batam",
        "Medan",
    ]

    text_lower = text.lower()

    detected = []

    for location in locations:

        if location.lower() in text_lower:
            detected.append(location)

    if detected:
        return ", ".join(dict.fromkeys(detected))

    return "Tidak diketahui"


# ============================================================
# 10. FUNGSI EKSTRAKSI GAJI
# ============================================================

def extract_salary(text):
    """
    Mendeteksi informasi gaji dari postingan.

    Fungsi menggunakan regex untuk mencari:
        Rp5.000.000
        5 juta per bulan
        UMK
        UMP

    Informasi yang ditemukan dikembalikan sebagai teks.
    """

    patterns = [
        r"Rp\s?[\d.,]+",
        r"\d+(?:[.,]\d+)?\s*(?:juta|jt)",
        r"\d+(?:[.,]\d+)?\s*(?:ribu|rb)",
        r"\bUMK\b",
        r"\bUMP\b",
    ]

    results = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        results.extend(matches)

    if results:

        return " | ".join(
            dict.fromkeys(results)
        )

    return "Tidak diketahui"

# ============================================================
#  FUNGSI EKSTRAKSI UMUR
# ============================================================

def extract_age(text):
    """
    Mengekstrak batas usia minimum dan maksimum.

    Contoh:
        Usia 18-30 tahun       -> (18, 30)
        Usia 20–40 tahun       -> (20, 40)
        Minimal usia 18 tahun  -> (18, None)
        Usia maksimal 25 tahun -> (None, 25)

    Jika informasi tidak ditemukan, hasilnya None.
    """

    text_lower = text.lower()

    min_age = None
    max_age = None

    # Pola rentang usia.
    range_pattern = re.search(
        r"\b(?:usia|umur)\s*"
        r"(\d{1,2})\s*"
        r"(?:-|–|sampai|s/d)\s*"
        r"(\d{1,2})\s*tahun\b",
        text_lower
    )

    if range_pattern:
        min_age = int(range_pattern.group(1))
        max_age = int(range_pattern.group(2))

        return min_age, max_age

    # Pola usia minimum.
    min_pattern = re.search(
        r"\b(?:minimal|min\.?|usia minimal|umur minimal)"
        r"\s*(?:usia|umur)?\s*(\d{1,2})\s*tahun\b",
        text_lower
    )

    # Pola usia maksimum.
    max_pattern = re.search(
        r"\b(?:maksimal|max\.?|usia maksimal|umur maksimal)"
        r"\s*(?:usia|umur)?\s*(\d{1,2})\s*tahun\b",
        text_lower
    )

    if min_pattern:
        min_age = int(min_pattern.group(1))

    if max_pattern:
        max_age = int(max_pattern.group(1))

    return min_age, max_age

# ============================================================
# FUNGSI EKSTRAKSI PENDIDIKAN 
# ============================================================

def extract_education(text):
    """
    Mengekstrak pendidikan minimum.

    Normalisasi:
        SMP/SMA       -> smp
        SMA/SMK       -> sma_smk
        SMP           -> smp
        SMA           -> sma_smk
        SMK           -> sma_smk
        SD            -> sd
        D3            -> d3
        S1            -> s1

    Mengutamakan tingkat pendidikan terendah
    jika posting menyebut beberapa jenjang.
    """

    text_lower = text.lower()

    education_patterns = [
        # Kombinasi jenjang. Periksa sebelum jenjang tunggal.
        (
            r"\bsmp\s*/\s*sma\b",
            "smp"
        ),
        (
            r"\bsma\s*/\s*smk\b|\bsmk\s*/\s*sma\b",
            "sma_smk"
        ),

        # Jenjang tunggal.
        (
            r"\b(?:smp|sekolah menengah pertama)\b",
            "smp"
        ),
        (
            r"\b(?:sma|smk|sekolah menengah atas|sekolah menengah kejuruan)\b",
            "sma_smk"
        ),
        (
            r"\b(?:sd|sekolah dasar)\b",
            "sd"
        ),
        (
            r"\b(?:d3|diploma 3)\b",
            "d3"
        ),
        (
            r"\b(?:s1|sarjana)\b",
            "s1"
        ),
    ]

    for pattern, education in education_patterns:

        if re.search(pattern, text_lower):
            return education

    return None


# ============================================================
# 11. FUNGSI EKSTRAKSI PERSYARATAN
# ============================================================

def extract_requirements(text):
    """
    Mengambil baris yang mengandung informasi persyaratan.

    Keyword yang diperiksa antara lain:
        usia, pendidikan, pengalaman, SIM,
        sertifikat, tinggi badan, dan kesehatan.

    Informasi tetap disimpan sebagai teks asli
    agar detail persyaratan tidak hilang.
    """

    keywords = [
        "kualifikasi",
        "persyaratan",
        "syarat",
        "usia",
        "pendidikan",
        "lulusan",
        "pengalaman",
        "bersedia",
        "memiliki",
        "sertifikat",
        "tinggi badan",
        "sehat jasmani",
        "tidak buta warna",
        "sim c",
        "sim a",
    ]

    results = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        line_lower = line.lower()

        if any(
            keyword in line_lower
            for keyword in keywords
        ):

            results.append(line)

    if results:
        return " | ".join(results)

    return "Tidak diketahui"


# ============================================================
# 12. FUNGSI EKSTRAKSI BENEFIT
# ============================================================

def extract_benefits(text):
    """
    Mendeteksi fasilitas atau benefit pekerjaan.

    Benefit yang dideteksi:
        BPJS
        Uang makan
        Transportasi
        BBM
        Lembur
        THR
        Mess
        Tunjangan
        Seragam

    Insentif akan tetap terdeteksi untuk sementara,
    tetapi nantinya perlu dipisahkan dari komponen benefit
    ke komponen kompensasi.
    """

    benefits = [
        "BPJS Kesehatan",
        "BPJS Ketenagakerjaan",
        "BPJS",
        "uang makan",
        "uang transport",
        "uang transportasi",
        "uang lembur",
        "THR",
        "makan siang",
        "mess",
        "tunjangan",
        "insentif",
        "seragam",
        "BBM",
        "bahan bakar",
    ]

    text_lower = text.lower()

    detected = []

    for benefit in benefits:

        if benefit.lower() in text_lower:

            detected.append(benefit)

    if detected:

        return " | ".join(
            dict.fromkeys(detected)
        )

    return "Tidak diketahui"


# ============================================================
# 13. FUNGSI EKSTRAKSI CARA MELAMAR DAN KONTAK
# ============================================================

def extract_application_method(text):
    """
    Mendeteksi metode pendaftaran lowongan.

    Contoh:
        WhatsApp, email, form, walk-in interview,
        atau aplikasi.

    Satu postingan bisa memiliki lebih dari satu metode.
    """

    methods = [
        "WhatsApp",
        "Email",
        "Google Form",
        "Form",
        "Walk-in Interview",
        "Aplikasi",
    ]

    text_lower = text.lower()

    detected = []

    for method in methods:

        if method.lower() in text_lower:
            detected.append(method)

    if detected:
        return " | ".join(dict.fromkeys(detected))

    return "Tidak diketahui"


def extract_contact(text):
    """
    Mengambil kemungkinan nomor telepon,
    email, dan URL pendaftaran.

    Hasil dikumpulkan menjadi satu field kontak.
    """

    patterns = [
        r"(?<!\d)(?:\+62|62|0)[\d\s\-()]{8,18}\d",
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        r"https?://[^\s<>]+",
    ]

    results = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        results.extend(matches)

    cleaned = []

    for item in results:

        item = item.strip(".,;:)")

        if item not in cleaned:
            cleaned.append(item)

    if cleaned:
        return " | ".join(cleaned)

    return "Tidak diketahui"


# ============================================================
# 14. FUNGSI EKSTRAKSI DEADLINE
# ============================================================

def detect_deadline(text):
    """
    Mendeteksi tanggal batas pendaftaran.

    Penting:
        Tidak semua tanggal di postingan merupakan deadline.
        Karena itu, fungsi ini hanya mencari tanggal yang
        muncul setelah label seperti:
        deadline, batas lamaran, paling lambat,
        atau ditutup pada.

    Format tanggal yang didukung:
        30/11/2026
        30-11-2026
        2026-11-30
        30 November 2026
        30 Nov 2026
    """

    month_mapping = {
        "januari": 1, "jan": 1,
        "februari": 2, "feb": 2,
        "maret": 3, "mar": 3,
        "april": 4, "apr": 4,
        "mei": 5,
        "juni": 6, "jun": 6,
        "juli": 7, "jul": 7,
        "agustus": 8, "agu": 8, "ags": 8,
        "september": 9, "sep": 9,
        "oktober": 10, "okt": 10,
        "november": 11, "nov": 11,
        "desember": 12, "des": 12,
    }

    # Cari bagian teks yang secara eksplisit menyebut deadline.
    label_pattern = (
        r"(?:deadline|batas\s+(?:akhir\s+)?lamaran|"
        r"paling\s+lambat|apply\s+before|closing\s+date|"
        r"ditutup\s+(?:pada|tanggal))"
    )

    label_match = re.search(
        label_pattern,
        text,
        re.IGNORECASE
    )

    if not label_match:
        return None

    # Ambil potongan teks setelah label deadline.
    segment = text[
        label_match.end():
        label_match.end() + 100
    ]

    # Format DD/MM/YYYY atau DD-MM-YYYY.
    match = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
        segment
    )

    if match:

        try:
            return date(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1))
            )

        except ValueError:
            pass

    # Format YYYY-MM-DD.
    match = re.search(
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
        segment
    )

    if match:

        try:
            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3))
            )

        except ValueError:
            pass

    # Format DD NamaBulan YYYY.
    month_names = "|".join(
        sorted(month_mapping, key=len, reverse=True)
    )

    match = re.search(
        rf"\b(\d{{1,2}})\s+({month_names})\s+(\d{{4}})\b",
        segment,
        re.IGNORECASE
    )

    if match:

        try:
            month = month_mapping[
                match.group(2).lower()
            ]

            return date(
                int(match.group(3)),
                month,
                int(match.group(1))
            )

        except ValueError:
            pass

    return None


# ============================================================
# 15. FUNGSI DETEKSI STATUS LOWONGAN
# ============================================================


def detect_job_status(text, posted_date):
    """
    Menentukan status lowongan berdasarkan umur postingan,
    bukti rekrutmen, dan informasi penutupan.

    Aturan umur:
        0-10 hari  : ACTIVE jika ada bukti rekrutmen.
        0-10 hari  : REVIEW jika bukti tidak cukup.
        11-20 hari : REVIEW.
        21-30 hari : REVIEW jika ada indikasi rekrutmen/kontak.
        >30 hari   : CLOSED (melewati batas umur crawler).

    Penutupan eksplisit dan deadline lewat selalu
    mengalahkan aturan umur postingan.
    """

    today = datetime.now(TIMEZONE).date()
    text_lower = text.lower()

    # --------------------------------------------------------
    # 1. Normalisasi tanggal postingan
    # --------------------------------------------------------

    if posted_date is None:
        return {
            "status": "REVIEW",
            "reason": "Tanggal postingan tidak tersedia",
            "deadline": "",
        }

    if posted_date.tzinfo is not None:
        posted_date = posted_date.astimezone(TIMEZONE)

    posted_date = posted_date.date()

    age_days = (today - posted_date).days

    # Tanggal masa depan tidak boleh dianggap aktif.
    if age_days < 0:
        return {
            "status": "REVIEW",
            "reason": "Tanggal postingan berada di masa depan",
            "deadline": "",
        }

    # --------------------------------------------------------
    # 2. Periksa bukti penutupan eksplisit
    # --------------------------------------------------------

    for keyword in CLOSED_KEYWORDS:
        if keyword in text_lower:
            return {
                "status": "CLOSED",
                "reason": f"Keyword penutupan ditemukan: {keyword}",
                "deadline": "",
            }

    # --------------------------------------------------------
    # 3. Periksa deadline
    # --------------------------------------------------------

    deadline = detect_deadline(text)

    if deadline and deadline < today:
        return {
            "status": "CLOSED",
            "reason": "Deadline pendaftaran sudah lewat",
            "deadline": deadline.isoformat(),
        }

    deadline_value = (
        deadline.isoformat()
        if deadline
        else ""
    )

    # --------------------------------------------------------
    # 4. Keyword bukti rekrutmen dan instruksi melamar
    # --------------------------------------------------------

    recruitment_keywords = [
        "we are hiring",
        "we're hiring",
        "open recruitment",
        "open vacancy",
        "hiring now",
        "lowongan kerja",
        "dibutuhkan",
        "dibuka lowongan",
        "posisi tersedia",
        "posisi yang dibutuhkan",
        "masih membuka lowongan",
        "apply now",
    ]

    application_keywords = [
        "kirim cv",
        "kirimkan cv",
        "kirim lamaran",
        "kirimkan lamaran",
        "lamaran dikirim ke",
        "apply melalui",
        "daftar melalui",
        "pendaftaran melalui",
        "submit your cv",
        "send your cv",
        "send your resume",
        "hubungi nomor",
        "hubungi whatsapp",
        "walk in interview",
    ]

    has_recruitment_evidence = any(
        keyword in text_lower
        for keyword in recruitment_keywords
    )

    has_application_evidence = any(
        keyword in text_lower
        for keyword in application_keywords
    )

    # Bukti minimum untuk mempertahankan postingan lama
    # dalam daftar review.
    has_contact = bool(
        re.search(
            r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
            text
        )
        or re.search(
            r"https?://\S+",
            text,
            re.IGNORECASE
        )
        or re.search(
            r"\b(?:wa|whatsapp)\b",
            text_lower
        )
        or re.search(
            r"(?<!\d)(?:\+62|62|0)[\d\s\-()]{8,18}\d",
            text
        )
    )

    has_active_evidence = (
        has_recruitment_evidence
        or has_application_evidence
        or (
            deadline is not None
            and deadline >= today
        )
    )

    has_review_evidence = (
        has_active_evidence
        or has_contact
    )

    # --------------------------------------------------------
    # 5. Posting berumur 0-10 hari
    # --------------------------------------------------------

    if age_days <= 10:

        if has_active_evidence:
            return {
                "status": "ACTIVE",
                "reason": (
                    f"Posting berusia {age_days} hari "
                    "dan memiliki bukti rekrutmen"
                ),
                "deadline": deadline_value,
            }

        return {
            "status": "REVIEW",
            "reason": (
                f"Posting berusia {age_days} hari, "
                "tetapi bukti rekrutmen belum cukup"
            ),
            "deadline": deadline_value,
        }

    # --------------------------------------------------------
    # 6. Posting berumur 11-20 hari
    # --------------------------------------------------------

    if age_days <= 20:
        return {
            "status": "REVIEW",
            "reason": (
                f"Posting berusia {age_days} hari "
                "dan masuk rentang review"
            ),
            "deadline": deadline_value,
        }

    # --------------------------------------------------------
    # 7. Posting berumur 21-30 hari
    # --------------------------------------------------------

    if age_days <= 30:

        if has_review_evidence:
            return {
                "status": "REVIEW",
                "reason": (
                    f"Posting berusia {age_days} hari "
                    "dan masih memiliki indikasi rekrutmen "
                    "atau informasi kontak"
                ),
                "deadline": deadline_value,
            }

        return {
            "status": "CLOSED",
            "reason": (
                f"Posting berusia {age_days} hari "
                "tanpa indikasi rekrutmen atau kontak"
            ),
            "deadline": deadline_value,
        }

    # --------------------------------------------------------
    # 8. Posting lebih dari 30 hari
    # --------------------------------------------------------

    return {
        "status": "CLOSED",
        "reason": (
            f"Posting berusia {age_days} hari, "
            "melewati batas umur crawler 30 hari"
        ),
        "deadline": deadline_value,
    }



# ============================================================
# 16. FUNGSI MENYIAPKAN FILE CSV
# ============================================================

FIELDNAMES = [
    "job_title",
    "company_name",
    "location",
    "job_category",
    "description",
    "gender",
    "min_age",
    "max_age",
    "education",
    "requirements",
    "salary",
    "employment_type",
    "benefits",
    "application_method",
    "contact",
    "deadline",
    "job_status",
    "status_reason",
    "source",
    "source_url",
    "posted_date",
    "crawled_at",
    "raw_text",
]


def prepare_csv():
    """
    Membuat folder output dan file CSV jika belum tersedia.

    Fungsi ini memastikan program tidak mengalami error
    ketika mencoba menyimpan data ke folder yang belum ada.

    Jika file sudah tersedia, data lama tetap dipertahankan.
    """

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    for filename in [ACTIVE_FILE, REVIEW_FILE, CLOSED_FILE]:

        if not os.path.exists(filename):

            with open(
                filename,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as file:

                writer = csv.DictWriter(
                    file,
                    fieldnames=FIELDNAMES
                )

                writer.writeheader()


# ============================================================
# 17. FUNGSI MEMBACA DATA YANG SUDAH ADA
# ============================================================

def get_existing_urls():
    """
    Membaca URL dari kedua file CSV.

    Tujuannya untuk menghindari duplikasi postingan
    ketika crawler dijalankan lebih dari satu kali.

    URL menjadi identitas unik sebuah postingan Telegram.
    """

    existing_urls = set()

    for filename in [ACTIVE_FILE, REVIEW_FILE, CLOSED_FILE]:

        if not os.path.exists(filename):
            continue

        with open(
            filename,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                url = row.get("source_url")

                if url:
                    existing_urls.add(url)

    return existing_urls


# ============================================================
# 18. FUNGSI MENYIMPAN DATA KE CSV
# ============================================================

def save_to_csv(data, filename):
    """
    Menambahkan satu data lowongan ke file CSV.

    Parameter:
        data     = dictionary berisi informasi lowongan.
        filename = file tujuan penyimpanan.

    Fungsi ini menggunakan mode append ('a')
    agar data baru ditambahkan tanpa menghapus data lama.
    """

    with open(
        filename,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES
        )

        writer.writerow(data)


# ============================================================
# 19. FUNGSI MEMPROSES SATU POSTINGAN
# ============================================================

def process_message(message, channel_name, source_url, extracted_text):
    """
    Mengubah satu pesan Telegram menjadi struktur data CSV.

    Fungsi ini menggabungkan hasil dari seluruh fungsi
    ekstraksi agar setiap postingan memiliki format data
    yang konsisten.

    Output:
        Dictionary yang siap disimpan ke CSV.
    """

    text = clean_text(extracted_text)

    status_data = detect_job_status(text, message.date)

    posted_date = (
        message.date.astimezone(TIMEZONE).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if message.date
        else ""
    )

    # Ekstraksi informasi gender.
    gender = "Tidak diketahui"

    if re.search(r"\b(pria|laki-laki)\b", text, re.I):
        gender = "Pria"

    if re.search(r"\b(wanita|perempuan)\b", text, re.I):
        gender = (
            "Pria/Wanita"
            if gender == "Pria"
            else "Wanita"
        )

    # Ekstraksi usia.
    min_age, max_age = extract_age(text)

    # Ekstraksi pendidikan.
    education = extract_education(text) or "Tidak diketahui"

    # Ekstraksi jenis pekerjaan.
    employment_type = "Tidak diketahui"

    for keyword in [
        "full-time",
        "full time",
        "part-time",
        "part time",
        "kontrak",
        "harian",
        "freelance",
        "magang",
        "tetap",
    ]:

        if keyword in text.lower():
            employment_type = keyword
            break

    # Susun seluruh data menjadi satu dictionary.
    data = {
        "job_title": extract_job_title(text),
        "company_name": extract_company(text),
        "location": extract_location(text),
        "job_category": detect_job_category(text),
        "description": text,
        "gender": gender,
        "min_age": min_age if min_age is not None else "",
        "max_age": max_age if max_age is not None else "",
        "education": education,
        "requirements": extract_requirements(text),
        "salary": extract_salary(text),
        "employment_type": employment_type,
        "benefits": extract_benefits(text),
        "application_method": extract_application_method(text),
        "contact": extract_contact(text),
        "deadline": status_data["deadline"],
        "job_status": status_data["status"],
        "status_reason": status_data["reason"],
        "source": f"Telegram: {channel_name}",
        "source_url": source_url,
        "posted_date": posted_date,
        "crawled_at": datetime.now(TIMEZONE).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "raw_text": text,
    }

    return data


# ============================================================
# 20. FUNGSI UTAMA CRAWLING TELEGRAM
# ============================================================

async def crawl_telegram():
    """
    Mengambil pesan dari channel Telegram publik.

    Alur kerja:
        1. Menyiapkan file CSV.
        2. Membaca URL yang sudah pernah diambil.
        3. Mengakses channel Telegram.
        4. Mengambil pesan sesuai batas yang ditentukan.
        5. Memfilter lowongan blue collar.
        6. Menghindari duplikasi.
        7. Memproses informasi lowongan.
        8. Memisahkan hasil berdasarkan status.
        9. Menampilkan ringkasan hasil crawling.

    Fungsi ini menggunakan async karena Telethon
    melakukan komunikasi dengan Telegram secara asynchronous.
    """

    if not CHANNELS:
        print("Belum ada channel yang dimasukkan.")
        return

    prepare_csv()

    existing_urls = get_existing_urls()
    
    # DEBUG: Periksa lokasi data duplikat.
    target_urls = {
        "https://t.me/ikjofficial/120006",
        "https://t.me/ikjofficial/120003",
        "https://t.me/ikjofficial/120002",
        "https://t.me/ikjofficial/119998",
        "https://t.me/ikjofficial/119996",
        "https://t.me/ikjofficial/119995",
        "https://t.me/ikjofficial/119993",
    }
    
    for filename in [ACTIVE_FILE, REVIEW_FILE, CLOSED_FILE]:
        if not os.path.exists(filename):
            continue
        
        with open(filename, "r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
    
            for row in reader:
                if row.get("source_url") in target_urls:
                    print(
                        f"[EXISTING] {row.get('source_url')} | "
                        f"Status: {row.get('job_status')} | "
                        f"File: {filename}"
                    )

    # Penghitung hasil crawling.
    stats = {
        "total": 0,
        "bluecollar": 0,
        "active": 0,
        "review": 0,
        "closed": 0,
        "duplicate": 0,
    }

    # Membuka koneksi Telegram.
    async with TelegramClient(
        "telegram_session",
        API_ID,
        API_HASH
    ) as client:

        for channel in CHANNELS:

            print(f"\nMengambil data: {channel}")
        
            try:
            
                # Ambil informasi channel.
                entity = await client.get_entity(channel)
        
                channel_name = (
                    getattr(entity, "username", None)
                    or str(channel).lstrip("@")
                )
        
                # Ambil pesan dari channel.
                messages = await client.get_messages(
                    entity,
                    limit=LIMIT_MESSAGES
                )
        
                for message in messages:
                
                    try:
                    
                        stats["total"] += 1
        
                        text = await extract_message_text(message)
        
                        if not text:
                            continue
                        
                        # Filter postingan blue collar.
                        if not is_bluecollar_job(text):
                            continue
                        
                        stats["bluecollar"] += 1
        
                        # Buat URL postingan Telegram.
                        source_url = (
                            f"https://t.me/"
                            f"{channel_name}/"
                            f"{message.id}"
                        )
        
                        # Periksa duplikasi.
                        if source_url in existing_urls:
                            print(f"[DUPLICATE] {source_url}")
                            stats["duplicate"] += 1
                            continue
                        
                        print(f"[NEW] {source_url}")
                        
                        # Proses data lowongan.
                        data = process_message(
                            message,
                            channel_name,
                            source_url,
                            text
                        )
        
                        # Pisahkan berdasarkan status lowongan.
                        if data["job_status"] == "ACTIVE":
                        
                            save_to_csv(data, ACTIVE_FILE)
                            stats["active"] += 1

                            print(f"[ACTIVE] {data['job_title']}")

                        elif data["job_status"] == "REVIEW":
                        
                            save_to_csv(data, REVIEW_FILE)
                            stats["review"] += 1

                            print(f"[REVIEW] {data['job_title']}")

                        elif data["job_status"] == "CLOSED":
                            
                            save_to_csv(data, CLOSED_FILE)
                            stats["closed"] += 1

                            print(f"[CLOSED] {data['job_title']}")

                        else:
                        
                            print(
                                f"[WARNING] Status tidak dikenal: "
                                f"{data['job_status']}"
                            )
        
                        existing_urls.add(source_url)
        
                    except Exception as error:
                    
                        print(
                            f"[ERROR] Pesan {message.id} "
                            f"di channel {channel}: {error}"
                        )
        
            except Exception as error:
            
                print(
                    f"[ERROR] Gagal mengakses channel "
                    f"{channel}: {error}"
                )

    # Tampilkan ringkasan hasil crawling.
    print("\n====================================")
    print("CRAWLING SELESAI")
    print("====================================")

    print(f"Total pesan diperiksa : {stats['total']}")
    print(f"Blue collar ditemukan : {stats['bluecollar']}")
    print(f"Lowongan aktif        : {stats['active']}")
    print(f"Perlu review          : {stats['review']}")
    print(f"Lowongan tutup        : {stats['closed']}")
    print(f"Duplikasi             : {stats['duplicate']}")

    print("\nFile output:")
    print(ACTIVE_FILE)
    print(REVIEW_FILE)
    print(CLOSED_FILE)


# ============================================================
# 21. PROGRAM ENTRY POINT
# ============================================================

# Bagian ini menjadi titik awal ketika file main.py dijalankan.
# asyncio.run() digunakan untuk menjalankan fungsi asynchronous.

if __name__ == "__main__":

    asyncio.run(
        crawl_telegram()
    )
