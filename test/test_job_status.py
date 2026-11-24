import os
import sys
import unittest

from datetime import datetime, timedelta

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

from main import (
    detect_job_status,
    detect_deadline,
    TIMEZONE,
)


class TestJobStatus(unittest.TestCase):

    def setUp(self):
        self.today = datetime.now(TIMEZONE).date()

    # ========================================================
    # 1. VALIDASI TANGGAL POSTINGAN
    # ========================================================

    def test_missing_posted_date(self):
        result = detect_job_status(
            "Dibutuhkan operator produksi. Kirim CV.",
            None
        )

        self.assertEqual(result["status"], "REVIEW")

    def test_future_posted_date(self):
        future_date = self.today + timedelta(days=1)

        result = detect_job_status(
            "Dibutuhkan operator produksi. Kirim CV.",
            future_date
        )

        self.assertEqual(result["status"], "REVIEW")

    # ========================================================
    # 2. POSTINGAN BARU
    # ========================================================

    def test_recent_job_with_recruitment_and_application(self):
        result = detect_job_status(
            (
                "Dibutuhkan operator produksi. "
                "Kirim CV sekarang melalui WhatsApp."
            ),
            self.today
        )

        self.assertEqual(result["status"], "ACTIVE")

    def test_recent_job_with_explicit_open_keyword(self):
        result = detect_job_status(
            (
                "Lowongan operator produksi masih dibuka. "
                "Silakan kirim lamaran."
            ),
            self.today
        )

        self.assertEqual(result["status"], "ACTIVE")

    def test_recent_job_without_recruitment_evidence(self):
        result = detect_job_status(
            "Informasi pekerjaan operator produksi.",
            self.today
        )

        self.assertEqual(result["status"], "REVIEW")

    def test_recent_job_with_contact_only(self):
        result = detect_job_status(
            (
                "Lowongan operator produksi. "
                "Hubungi WhatsApp 081234567890."
            ),
            self.today
        )

        self.assertEqual(result["status"], "REVIEW")

    # ========================================================
    # 3. POSTINGAN LAMA
    # ========================================================

    def test_job_age_11_to_20_days(self):
        posted_date = self.today - timedelta(days=15)

        result = detect_job_status(
            (
                "Dibutuhkan operator produksi. "
                "Kirim CV sekarang."
            ),
            posted_date
        )

        self.assertEqual(result["status"], "REVIEW")

    def test_job_age_21_to_30_days_with_contact(self):
        posted_date = self.today - timedelta(days=25)

        result = detect_job_status(
            (
                "Lowongan operator produksi. "
                "Hubungi WhatsApp."
            ),
            posted_date
        )

        self.assertEqual(result["status"], "REVIEW")

    def test_job_age_21_to_30_days_without_evidence(self):
        posted_date = self.today - timedelta(days=25)

        result = detect_job_status(
            "Informasi pekerjaan operator produksi.",
            posted_date
        )

        self.assertEqual(result["status"], "REVIEW")

    def test_job_age_over_30_days(self):
        posted_date = self.today - timedelta(days=31)

        result = detect_job_status(
            (
                "Dibutuhkan operator produksi. "
                "Kirim CV sekarang."
            ),
            posted_date
        )

        self.assertEqual(result["status"], "REVIEW")

    # ========================================================
    # 4. DETEKSI PENUTUPAN LOWONGAN
    # ========================================================

    def test_explicitly_closed_job(self):
        result = detect_job_status(
            "Lowongan sudah ditutup.",
            self.today
        )

        self.assertEqual(result["status"], "CLOSED")

    def test_expired_deadline(self):
        expired_date = self.today - timedelta(days=1)

        deadline_text = (
            f"Dibutuhkan operator produksi. "
            f"Deadline: {expired_date.strftime('%d-%m-%Y')}"
        )

        result = detect_job_status(
            deadline_text,
            self.today
        )

        self.assertEqual(result["status"], "CLOSED")

    # ========================================================
    # 5. DEADLINE YANG BELUM LEWAT
    # ========================================================

    def test_future_deadline_without_application_evidence(self):
        future_deadline = self.today + timedelta(days=5)

        deadline_text = (
            f"Informasi lowongan operator produksi. "
            f"Deadline: {future_deadline.strftime('%d-%m-%Y')}"
        )

        result = detect_job_status(
            deadline_text,
            self.today
        )

        self.assertEqual(result["status"], "REVIEW")

    def test_future_deadline_with_application_evidence(self):
        future_deadline = self.today + timedelta(days=5)

        deadline_text = (
            f"Dibutuhkan operator produksi. "
            f"Kirim CV sekarang. "
            f"Deadline: {future_deadline.strftime('%d-%m-%Y')}"
        )

        result = detect_job_status(
            deadline_text,
            self.today
        )

        self.assertEqual(result["status"], "ACTIVE")

    # ========================================================
    # 6. KONFLIK BUKTI STATUS LOWONGAN
    # ========================================================

    def test_closed_keyword_overrides_active_evidence(self):
        result = detect_job_status(
            (
                "Lowongan operator produksi masih dibuka. "
                "Namun lowongan sudah ditutup."
            ),
            self.today
        )

        self.assertEqual(result["status"], "CLOSED")

    def test_expired_deadline_overrides_active_evidence(self):
        expired_date = self.today - timedelta(days=1)

        result = detect_job_status(
            (
                "Dibutuhkan operator produksi. "
                "Kirim CV sekarang. "
                f"Deadline: {expired_date.strftime('%d-%m-%Y')}"
            ),
            self.today
        )

        self.assertEqual(result["status"], "CLOSED")

    def test_active_evidence_with_future_deadline(self):
        future_deadline = self.today + timedelta(days=5)

        result = detect_job_status(
            (
                "Dibutuhkan operator produksi. "
                "Kirim CV sekarang. "
                f"Deadline: {future_deadline.strftime('%d-%m-%Y')}"
            ),
            self.today
        )

        self.assertEqual(result["status"], "ACTIVE")

    def test_closed_keyword_without_other_evidence(self):
        result = detect_job_status(
            "Informasi lowongan sudah ditutup.",
            self.today
        )

        self.assertEqual(result["status"], "CLOSED")

class TestDeadlineExtractor(unittest.TestCase):

    def test_deadline_numeric_format(self):
        result = detect_deadline(
            "Deadline: 30-11-2026"
        )

        from datetime import date

        self.assertEqual(
            result,
            date(2026, 11, 30)
        )

    def test_deadline_month_name(self):
        result = detect_deadline(
            "Batas lamaran: 30 November 2026"
        )

        from datetime import date

        self.assertEqual(
            result,
            date(2026, 11, 30)
        )

    def test_date_without_deadline_label(self):
        result = detect_deadline(
            "Interview akan dilaksanakan pada 30 November 2026"
        )

        self.assertIsNone(result)
        
        
if __name__ == "__main__":
    unittest.main()