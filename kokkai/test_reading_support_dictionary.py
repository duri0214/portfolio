from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from kokkai.domain.service.reading_support import ReadingSupportService
from kokkai.domain.service.reading_support_import import ReadingSupportCsvImporter
from kokkai.models import ReadingSupportEntry


class ReadingSupportEntryTests(TestCase):
    """辞書エントリーの入力規則と読み仮名支援への反映を確認する。"""

    def test_word_requires_reading_and_description(self):
        """
        シナリオ:
        - 入力: 説明が空の項目と、読み・説明を持つ項目。
        - 処理: 両方の項目を検証する。
        - 期待値: 説明が空の項目は拒否され、読み・説明を持つ項目は保存できる。
        """
        without_description = ReadingSupportEntry(
            word="説明なし単語",
            reading="せつめいなしたんご",
        )
        with self.assertRaises(ValidationError):
            without_description.full_clean()

        valid_entry = ReadingSupportEntry(
            word="説明付き単語",
            reading="せつめいつきたんご",
            description="単語の説明",
        )
        valid_entry.full_clean()
        valid_entry.save()
        self.assertTrue(
            ReadingSupportEntry.objects.filter(word="説明付き単語").exists()
        )

    def test_db_entry_uses_reading_and_description_together(self):
        """
        シナリオ:
        - 入力: 読みと説明の両方を持つ辞書項目。
        - 処理: DB辞書を使って本文を解析する。
        - 期待値: 同じセグメントに優先読みと説明情報が保持される。
        """
        ReadingSupportEntry.objects.create(
            word="NISA",
            reading="ニーサ",
            description="少額投資非課税制度",
            source_url="https://example.com/nisa",
        )

        annotation = ReadingSupportService().annotate("NISA")

        entry_segment = next(
            segment for segment in annotation.segments if segment.text == "NISA"
        )
        self.assertEqual(entry_segment.reading, "ニーサ")
        self.assertEqual(entry_segment.entry.description, "少額投資非課税制度")


class ReadingSupportCsvImporterTests(TestCase):
    """CSVの登録、再取り込み、エラー時の一括取り消しを確認する。"""

    HEADER = "word,reading,description,source_url\n"

    def test_import_upserts_existing_word_even_when_content_is_unchanged(self):
        """
        シナリオ:
        - 入力: 同じ単語のCSVを再取り込みし、その後に説明を変えたCSVを取り込む。
        - 処理: CSV取り込みを3回実行する。
        - 期待値: 既存単語は同一内容でも上書き対象として扱われ、変更内容も反映される。
        """
        csv_text = (
            self.HEADER + "NISA,ニーサ,少額投資非課税制度,https://example.com/nisa\n"
        )
        importer = ReadingSupportCsvImporter()

        first = importer.import_csv(csv_text)
        second = importer.import_csv(csv_text)
        changed_csv = csv_text.replace("少額投資非課税制度", "更新後の説明")
        updated = importer.import_csv(changed_csv)

        self.assertEqual((first.created, first.updated), (1, 0))
        self.assertEqual((second.created, second.updated), (0, 1))
        self.assertEqual((updated.created, updated.updated), (0, 1))
        self.assertEqual(
            ReadingSupportEntry.objects.get(word="NISA").description,
            "更新後の説明",
        )

    def test_blank_description_is_rejected(self):
        """
        シナリオ:
        - 入力: 説明が空のCSV行。
        - 処理: CSVを取り込む。
        - 期待値: 説明が必須のためエラーになり、項目は保存されない。
        """
        result = ReadingSupportCsvImporter().import_csv(
            self.HEADER + "新規読み補正,しんきよみほせい,,\n"
        )

        self.assertFalse(result.is_success)
        self.assertIn("説明を入力してください", result.errors[0].message)
        self.assertFalse(
            ReadingSupportEntry.objects.filter(word="新規読み補正").exists()
        )

    def test_invalid_rows_are_reported_without_partial_import(self):
        """
        シナリオ:
        - 入力: 有効行と、読みが空の無効行を含むCSV。
        - 処理: CSV全体を検証する。
        - 期待値: エラーを表示し、有効行も保存しない。
        """
        result = ReadingSupportCsvImporter().import_csv(
            self.HEADER
            + "NISA,ニーサ,少額投資非課税制度,https://example.com/nisa\n"
            + "invalid-word,,説明,https://example.com/invalid\n"
        )

        self.assertFalse(result.is_success)
        self.assertEqual(result.errors[0].line_number, 3)
        self.assertFalse(ReadingSupportEntry.objects.filter(word="NISA").exists())


class ReadingSupportManagementViewTests(TestCase):
    """辞書の管理、CSV取り込み、権限を確認する。"""

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
        シナリオ:
        - 入力: 一般ユーザーによる辞書管理画面へのアクセス。
        - 処理: 一覧とCSV取り込み画面を開く。
        - 期待値: どちらもHTTP 403になる。
        """
        self.client.force_login(self.regular_user)
        for view_name in (
            "kokkai:reading_support_management",
            "kokkai:reading_support_csv_import",
        ):
            response = self.client.get(reverse(view_name))
            self.assertEqual(response.status_code, 403)

    def test_manual_create_page_is_not_available(self):
        """
        シナリオ:
        - 入力: 手動追加画面のURL名。
        - 処理: URLを逆引きする。
        - 期待値: 新規追加画面は提供されない。
        """
        with self.assertRaises(NoReverseMatch):
            reverse("kokkai:reading_support_entry_create")

    def test_existing_entry_can_be_edited(self):
        """
        シナリオ:
        - 入力: 登録済み項目と、スーパーユーザーによる更新内容。
        - 処理: 編集画面から保存する。
        - 期待値: CSVで追加した項目を後から編集できる。
        """
        entry = ReadingSupportEntry.objects.create(
            word="NISA",
            reading="ニーサ",
            description="少額投資非課税制度",
            source_url="https://example.com/nisa",
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("kokkai:reading_support_entry_update", args=[entry.pk]),
            {
                "word": "NISA",
                "reading": "ニーサ",
                "description": "更新後の説明",
                "source_url": "https://example.com/nisa",
            },
        )

        self.assertRedirects(response, reverse("kokkai:reading_support_management"))
        entry.refresh_from_db()
        self.assertEqual(entry.description, "更新後の説明")

    def test_csv_import_view_imports_uploaded_file(self):
        """
        シナリオ:
        - 入力: スーパーユーザーと有効な辞書CSV。
        - 処理: CSV取り込み画面からアップロードする。
        - 期待値: 新規の単語が保存され、管理画面へ戻る。
        """
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("kokkai:reading_support_csv_import"),
            {
                "file": SimpleUploadedFile(
                    "dictionary.csv",
                    (
                        "word,reading,description,source_url\n"
                        "csv-term,csv-reading,csv description,https://example.com/csv\n"
                    ).encode("utf-8"),
                    content_type="text/csv",
                )
            },
        )

        self.assertRedirects(response, reverse("kokkai:reading_support_management"))
        self.assertTrue(ReadingSupportEntry.objects.filter(word="csv-term").exists())
