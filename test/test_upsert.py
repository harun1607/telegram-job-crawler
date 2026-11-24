
import os
import sys
import csv
import tempfile
import unittest

from unittest.mock import patch

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

import main


class TestUpsertInsert(unittest.TestCase):

    def setUp(self):
        # Gunakan folder sementara agar output asli tidak berubah.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.active_file = os.path.join(
            self.temp_dir.name,
            "lowongan_aktif.csv"
        )

        self.review_file = os.path.join(
            self.temp_dir.name,
            "lowongan_review.csv"
        )

        self.closed_file = os.path.join(
            self.temp_dir.name,
            "lowongan_tutup.csv"
        )

        # Arahkan seluruh file CSV ke folder sementara.
        self.patches = [
            patch.object(main, "OUTPUT_DIR", self.temp_dir.name),
            patch.object(main, "ACTIVE_FILE", self.active_file),
            patch.object(main, "REVIEW_FILE", self.review_file),
            patch.object(main, "CLOSED_FILE", self.closed_file),
        ]

        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

        main.prepare_csv()

        self.existing_jobs = {}

        self.job_data = {
            "source_url": "https://t.me/testchannel/100",
            "job_title": "Operator Produksi",
            "job_status": "ACTIVE",
        }

    def test_insert_new_job(self):

        result = main.upsert_to_csv(
            self.job_data,
            self.existing_jobs
        )

        # Pastikan hasil UPSERT adalah inserted.
        self.assertEqual(result, "inserted")

        # Pastikan data masuk ke file aktif.
        with open(
            self.active_file,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            rows = list(csv.DictReader(file))

        # Pastikan hanya ada satu data baru.
        self.assertEqual(len(rows), 1)

        self.assertEqual(
            rows[0]["source_url"],
            self.job_data["source_url"]
        )

        self.assertEqual(
            rows[0]["job_title"],
            self.job_data["job_title"]
        )

        # Pastikan data tercatat dalam existing_jobs.
        self.assertIn(
            self.job_data["source_url"],
            self.existing_jobs
        )
        


    def test_duplicate_job_is_not_inserted_twice(self):

        # INSERT pertama.
        first_result = main.upsert_to_csv(
            self.job_data,
            self.existing_jobs
        )

        # INSERT kedua dengan source_url yang sama.
        second_result = main.upsert_to_csv(
            self.job_data,
            self.existing_jobs
        )

        # Hasil pertama harus inserted.
        self.assertEqual(first_result, "inserted")

        # Hasil kedua harus unchanged.
        self.assertEqual(second_result, "unchanged")

        # Baca isi CSV.
        with open(
            self.active_file,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            rows = list(csv.DictReader(file))

        # Pastikan tidak ada baris duplikat.
        self.assertEqual(len(rows), 1)

        self.assertEqual(
            rows[0]["source_url"],
            self.job_data["source_url"]
        )


    def test_update_existing_job(self):

        # INSERT data awal.
        first_result = main.upsert_to_csv(
            self.job_data,
            self.existing_jobs
        )

        # Ubah judul pekerjaan.
        updated_job = self.job_data.copy()
        updated_job["job_title"] = "Staff Administrasi"

        # Jalankan UPSERT dengan data terbaru.
        second_result = main.upsert_to_csv(
            updated_job,
            self.existing_jobs
        )

        # Pastikan INSERT pertama berhasil.
        self.assertEqual(first_result, "inserted")

        # Pastikan data lama berhasil diperbarui.
        self.assertEqual(second_result, "updated")

        # Baca isi CSV.
        with open(
            self.active_file,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            rows = list(csv.DictReader(file))

        # Pastikan tidak ada duplikasi.
        self.assertEqual(len(rows), 1)

        # Pastikan judul terbaru tersimpan.
        self.assertEqual(
            rows[0]["job_title"],
            "Staff Administrasi"
        )

        # Pastikan source URL tetap sama.
        self.assertEqual(
            rows[0]["source_url"],
            self.job_data["source_url"]
        )
        
    def test_status_change_moves_job_to_closed_file(self):
    
        # 1. Masukkan data awal dengan status ACTIVE.
        first_result = main.upsert_to_csv(
            self.job_data,
            self.existing_jobs
        )
    
        # 2. Ubah status pekerjaan menjadi CLOSED.
        closed_job = self.job_data.copy()
        closed_job["job_status"] = "CLOSED"
    
        # 3. Jalankan UPSERT kembali.
        second_result = main.upsert_to_csv(
            closed_job,
            self.existing_jobs
        )
    
        # 4. Pastikan proses INSERT dan UPDATE berhasil.
        self.assertEqual(first_result, "inserted")
        self.assertEqual(second_result, "updated")
    
        # 5. Baca active.csv.
        with open(
            self.active_file,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as file:
            active_rows = list(csv.DictReader(file))
    
        # 6. Baca closed.csv.
        with open(
            self.closed_file,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as file:
            closed_rows = list(csv.DictReader(file))
    
        # 7. Pastikan data sudah keluar dari active.csv.
        self.assertEqual(len(active_rows), 0)
    
        # 8. Pastikan data masuk ke closed.csv.
        self.assertEqual(len(closed_rows), 1)
    
        # 9. Pastikan status terbaru tersimpan.
        self.assertEqual(
            closed_rows[0]["job_status"],
            "CLOSED"
        )
    
        # 10. Pastikan URL tetap sama.
        self.assertEqual(
            closed_rows[0]["source_url"],
            self.job_data["source_url"]
        )
    
        # 11. Pastikan existing_jobs menunjuk ke file tujuan.
        self.assertEqual(
            self.existing_jobs[self.job_data["source_url"]]["filename"],
            self.closed_file
        )



if __name__ == "__main__":
    unittest.main()
