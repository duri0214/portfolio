from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from kokkai.domain.service.reading_support import ReadingSupportService
from kokkai.domain.service.reading_support_import import ReadingSupportCsvImporter
from kokkai.models import ReadingSupportEntry


class ReadingSupportEntryTests(TestCase):
    """辞書エントリーの入力規則と読み仮名支援への反映を確認する。"""

    def test_description_distinguishes_terms_from_reading_overrides(self):
        """
        Scenario:
        - Create an item with an incomplete description and an item without a description.
        - Validate both entries.
        - The incomplete description is rejected and the empty description is accepted.
        """
        term = ReadingSupportEntry(
            surface="term-without-definition",
            reading="term-reading",
            description="説明だけ",
        )
        with self.assertRaises(ValidationError):
            term.full_clean()

        override = ReadingSupportEntry(
            surface="reading-override",
            reading="override-reading",
        )
        override.full_clean()
        override.save()
        self.assertTrue(
            ReadingSupportEntry.objects.filter(surface="reading-override").exists()
        )

    def test_db_entries_are_used_for_annotation(self):
        """
        Scenario:
        - Add a dictionary entry and annotate text containing it.
        - The entry is used for annotation.
        """
        ReadingSupportEntry.objects.create(
            surface="NISA",
            normalized_surface="nisa",
            reading="nisa-reading",
            description="a description",
            source_url="https://example.com/nisa",
        )

        annotation = ReadingSupportService().annotate("NISA")

        self.assertTrue(
            any(
                segment.term and segment.term.surface == "NISA"
                for segment in annotation.segments
            )
        )


class ReadingSupportCsvImporterTests(TestCase):
    """CSVの登録、再取り込み、エラー時の一括取り消しを確認する。"""

    HEADER = "surface,reading,description,source_url\n"

    def test_import_is_idempotent_and_update_requires_explicit_option(self):
        """
        Scenario:
        - Import the same term twice and then import changed content.
        - Repeat the changed import with the update option.
        - The second import is skipped, the first changed import fails, and the
          explicit update changes the existing entry.
        """
        csv_text = (
            self.HEADER + "NISA,nisa-reading,a description,https://example.com/nisa\n"
        )
        importer = ReadingSupportCsvImporter()

        first = importer.import_csv(csv_text)
        second = importer.import_csv(csv_text)
        changed_csv = csv_text.replace("a description", "a changed description")
        changed = importer.import_csv(changed_csv)
        updated = importer.import_csv(changed_csv, update_existing=True)

        self.assertEqual((first.created, first.updated, first.skipped), (1, 0, 0))
        self.assertEqual((second.created, second.updated, second.skipped), (0, 0, 1))
        self.assertEqual(len(changed.errors), 1)
        self.assertEqual((updated.created, updated.updated, updated.skipped), (0, 1, 0))
        self.assertEqual(
            ReadingSupportEntry.objects.get(surface="NISA").description,
            "a changed description",
        )

    def test_blank_definition_columns_create_a_reading_override(self):
        """
        Scenario:
        - Import a CSV row with an empty definition and source URL.
        - The importer treats it as a reading override.
        """
        result = ReadingSupportCsvImporter().import_csv(
            self.HEADER + "reading-override,override-reading,,\n"
        )

        self.assertTrue(result.is_success)
        entry = ReadingSupportEntry.objects.get(surface="reading-override")
        self.assertFalse(entry.is_term)

    def test_invalid_rows_are_reported_without_partial_import(self):
        """
        Scenario:
        - Import one valid term and one invalid term in the same CSV.
        - The importer validates all rows before saving.
        - The error is reported and the valid row is not saved either.
        """
        result = ReadingSupportCsvImporter().import_csv(
            self.HEADER
            + "NISA,nisa-reading,a description,https://example.com/nisa\n"
            + "invalid-term,,invalid description,https://example.com/invalid\n"
        )

        self.assertFalse(result.is_success)
        self.assertEqual(result.errors[0].line_number, 3)
        self.assertFalse(ReadingSupportEntry.objects.filter(surface="NISA").exists())


class ReadingSupportManagementViewTests(TestCase):
    """Test dictionary management and CSV import permissions and registration."""

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="reading-support-admin",
            email="admin@example.com",
            password="test-password",
        )
        self.regular_user = User.objects.create_user(
            username="reading-support-user",
            password="test-password",
        )

    def test_management_pages_require_a_superuser(self):
        """
        Scenario:
        - A regular user requests dictionary management pages.
        - The management and CSV pages are protected.
        - Each request returns HTTP 403.
        """
        self.client.force_login(self.regular_user)
        for view_name in (
            "kokkai:reading_support_management",
            "kokkai:reading_support_csv_import",
        ):
            response = self.client.get(reverse(view_name))
            self.assertEqual(response.status_code, 403)

    def test_reading_support_form_uses_bootstrap_widgets(self):
        """
        Scenario:
        - Open the manual dictionary entry form.
        - The form uses Bootstrap controls and only exposes the current fields.
        """
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("kokkai:reading_support_entry_create"))

        self.assertContains(response, 'class="form-control"')
        self.assertNotContains(response, 'name="entry_type"')
        self.assertNotContains(response, 'name="category"')

    def test_entry_form_creates_a_dictionary_entry(self):
        """
        Scenario:
        - A superuser submits the manual dictionary entry form.
        - The form redirects to management.
        - The new term is available in the dictionary.
        """
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("kokkai:reading_support_entry_create"),
            {
                "surface": "manual-term",
                "reading": "manual-reading",
                "description": "manual description",
                "source_url": "https://example.com/manual",
            },
        )

        self.assertRedirects(response, reverse("kokkai:reading_support_management"))
        entry = ReadingSupportEntry.objects.get(surface="manual-term")
        self.assertEqual(entry.description, "manual description")

    def test_csv_import_view_imports_uploaded_file(self):
        """
        Scenario:
        - A superuser uploads a valid dictionary CSV.
        - The CSV import view redirects to management.
        - The uploaded term is saved.
        """
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("kokkai:reading_support_csv_import"),
            {
                "file": SimpleUploadedFile(
                    "dictionary.csv",
                    (
                        "surface,reading,description,source_url\n"
                        "csv-term,csv-reading,csv description,https://example.com/csv\n"
                    ).encode("utf-8"),
                    content_type="text/csv",
                )
            },
        )

        self.assertRedirects(response, reverse("kokkai:reading_support_management"))
        self.assertTrue(ReadingSupportEntry.objects.filter(surface="csv-term").exists())
