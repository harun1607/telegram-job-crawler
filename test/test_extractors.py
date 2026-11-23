import os
import sys
import unittest

# Atur dummy credential sebelum import main.py.
os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "dummy_hash")

# Tambahkan root project ke Python path.
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

# Import fungsi setelah konfigurasi selesai.
from main import (
    extract_age,
    extract_education,
    extract_job_title,
    detect_job_category,
    extract_location,
    extract_requirements,
    extract_benefits,
    extract_application_method,
    extract_contact,
)


class TestJobExtractors(unittest.TestCase):

    def setUp(self):

        self.operator_text = """
        1. Operator Produksi
        [Nama Perusahaan] – Kawasan Industri Cikarang

        Dibutuhkan segera Operator Produksi (Pria/Wanita)

        Kualifikasi:
        Usia 18–30 tahun
        Pendidikan min. SMA/SMK sederajat
        Sehat jasmani & rohani, tidak buta warna
        Bersedia kerja shift
        Fresh graduate dipersilakan melamar

        Benefit:
        Gaji sesuai UMK, uang lembur,
        BPJS Kesehatan & Ketenagakerjaan,
        makan siang

        Kirim lamaran via WhatsApp:
        08xx-xxxx-xxxx

        Tidak dipungut biaya apa pun!
        """

        self.driver_text = """
        2. Kurir / Delivery Driver (Motor)
        [Nama Perusahaan] – Area Jakarta Selatan

        Kualifikasi:
        Pria, usia 20–40 tahun
        Min. SMP/SMA sederajat
        Memiliki motor sendiri & SIM C aktif
        Memiliki smartphone Android
        Menguasai area sekitar

        Benefit:
        Gaji pokok + insentif per paket,
        BBM ditanggung, BPJS

        Daftar: [link form / nomor WA]
        """

    def test_operator_job_title(self):

        result = extract_job_title(
            self.operator_text
        )

        self.assertEqual(
            result,
            "Operator Produksi"
        )

    def test_driver_job_title(self):

        result = extract_job_title(
            self.driver_text
        )

        self.assertIn(
            "Kurir",
            result
        )

    def test_operator_category(self):

        result = detect_job_category(
            self.operator_text
        )

        self.assertEqual(
            result,
            "Operator Produksi"
        )

    def test_driver_category(self):

        result = detect_job_category(
            self.driver_text
        )

        self.assertEqual(
            result,
            "Transportasi"
        )

    def test_operator_location(self):

        result = extract_location(
            self.operator_text
        )

        self.assertIn(
            "Cikarang",
            result
        )

    def test_driver_location(self):

        result = extract_location(
            self.driver_text
        )

        self.assertIn(
            "Jakarta Selatan",
            result
        )

    def test_operator_requirements(self):

        result = extract_requirements(
            self.operator_text
        )

        self.assertIn(
            "tidak buta warna",
            result.lower()
        )

        self.assertIn(
            "bersedia kerja shift",
            result.lower()
        )

    def test_driver_requirements(self):

        result = extract_requirements(
            self.driver_text
        )

        self.assertIn(
            "SIM C",
            result
        )

        self.assertIn(
            "smartphone Android",
            result
        )

    def test_operator_benefits(self):

        result = extract_benefits(
            self.operator_text
        )

        self.assertIn(
            "BPJS",
            result
        )

        self.assertIn(
            "makan",
            result.lower()
        )

    def test_driver_benefits(self):

        result = extract_benefits(
            self.driver_text
        )

        self.assertIn(
            "BBM",
            result
        )

        self.assertIn(
            "insentif",
            result.lower()
        )

    def test_operator_application_method(self):

        result = extract_application_method(
            self.operator_text
        )

        self.assertIn(
            "WhatsApp",
            result
        )

    def test_operator_contact_placeholder(self):

        result = extract_contact(
            self.operator_text
        )

        # Placeholder bukan nomor telepon valid.
        self.assertNotIn(
            "08xx",
            result
        )

    def test_operator_age(self):

        result = extract_age(self.operator_text)

        self.assertEqual(result, (18, 30))


    def test_driver_age(self):

        result = extract_age(self.driver_text)

        self.assertEqual(result, (20, 40))


    def test_operator_education(self):

        result = extract_education(self.operator_text)

        self.assertEqual(result, "sma_smk")


    def test_driver_education(self):

        result = extract_education(self.driver_text)

        self.assertEqual(result, "smp")


    def test_missing_age(self):

        result = extract_age(
            "Pendidikan minimal SMA sederajat"
        )

        self.assertEqual(result, (None, None))


    def test_missing_education(self):

        result = extract_education(
            "Dibutuhkan segera pekerja produksi"
        )

        self.assertIsNone(result)

if __name__ == "__main__":

    unittest.main()