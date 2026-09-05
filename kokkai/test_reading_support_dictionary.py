from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from kokkai.domain.service.reading_support import ReadingSupportService
from kokkai.domain.service.reading_support_draft import ReadingSupportDraftService
from kokkai.domain.service.reading_support_import import ReadingSupportCsvImporter
from kokkai.models import ReadingSupportEntry


class ReadingSupportEntryTests(TestCase):
    """DB辞書の検証、無効化、既存サービスへの反映を確認する。"""

    def test_term_requires_definition_metadata_but_override_does_not(self):
        """
        シナリオ:
        - 入力: 説明・カテゴリ・出典URLがない用語と、読みだけの補正。
        - 処理: それぞれモデルの完全検証を行う。
        - 期待値: 用語は拒否され、読み補正は登録できる。
        """
        term = ReadingSupportEntry(
            surface="用語",
            reading="ヨウゴ",
            entry_type=ReadingSupportEntry.EntryType.TERM,
        )
        with self.assertRaises(ValidationError):
            term.full_clean()

        override = ReadingSupportEntry(
            surface="お諮り以外",
            reading="ヨミ",
            entry_type=ReadingSupportEntry.EntryType.READING_OVERRIDE,
        )
        override.full_clean()
        override.save()
        self.assertEqual(ReadingSupportEntry.objects.count(), 3)

    def test_active_db_entries_are_used_and_inactive_entries_are_ignored(self):
        """
        シナリオ:
        - 入力: DBへ用語を追加した後、同じエントリを無効化する。
        - 処理: DBから辞書を構築して本文を解析する。
        - 期待値: 有効時だけ用語情報が表示対象になる。
        """
        entry = ReadingSupportEntry.objects.create(
            surface="NISA",
            normalized_surface="nisa",
            reading="ニーサ",
            description="少額投資非課税制度",
            category="制度",
            source_url="https://example.com/nisa",
        )

        annotation = ReadingSupportService().annotate("NISAを確認します。")
        self.assertEqual(annotation.segments[0].term.surface, "NISA")

        entry.is_active = False
        entry.save(update_fields=["is_active", "updated_at"])
        annotation = ReadingSupportService().annotate("NISAを確認します。")
        self.assertFalse(any(segment.term for segment in annotation.segments))


class ReadingSupportCsvImporterTests(TestCase):
    """CSV形式、エラー行、再取り込み、更新モードを確認する。"""

    HEADER = "surface,reading,description,category,source_url\n"

    def test_import_is_idempotent_and_update_requires_explicit_option(self):
        """
        シナリオ:
        - 入力: 同じ用語CSVを2回、説明を変更したCSVを更新なし・更新ありで渡す。
        - 処理: CSV取り込みサービスを順番に実行する。
        - 期待値: 再取り込みはスキップされ、変更は明示した場合だけ更新される。
        """
        csv_text = (
            self.HEADER
            + "NISA,ニーサ,少額投資非課税制度,制度,https://example.com/nisa\n"
        )
        importer = ReadingSupportCsvImporter()

        first = importer.import_csv(csv_text)
        second = importer.import_csv(csv_text)
        changed = importer.import_csv(
            csv_text.replace("少額投資非課税制度", "少額投資非課税制度の説明")
        )
        updated = importer.import_csv(
            csv_text.replace("少額投資非課税制度", "少額投資非課税制度の説明"),
            update_existing=True,
        )

        self.assertEqual((first.created, first.updated, first.skipped), (1, 0, 0))
        self.assertEqual((second.created, second.updated, second.skipped), (0, 0, 1))
        self.assertEqual(len(changed.errors), 1)
        self.assertEqual((updated.created, updated.updated, updated.skipped), (0, 1, 0))
        self.assertEqual(
            ReadingSupportEntry.objects.get(surface="NISA").description,
            "少額投資非課税制度の説明",
        )

    def test_blank_definition_columns_create_a_reading_override(self):
        """
        シナリオ:
        - 入力: 説明・カテゴリ・出典URLが空のCSV行。
        - 処理: エントリ種別を省略して取り込む。
        - 期待値: 用語ではなく読み補正として登録される。
        """
        result = ReadingSupportCsvImporter().import_csv(
            self.HEADER + "読み補正,ヨミホセイ,,,\n"
        )

        self.assertTrue(result.is_success)
        entry = ReadingSupportEntry.objects.get(surface="読み補正")
        self.assertEqual(
            entry.entry_type, ReadingSupportEntry.EntryType.READING_OVERRIDE
        )

    def test_invalid_rows_are_reported_without_partial_import(self):
        """
        シナリオ:
        - 入力: 正しい行と出典URLがない用語行を含むCSV。
        - 処理: 全行を検証してから保存する。
        - 期待値: 行番号と理由が返り、正しい行も含めて保存されない。
        """
        result = ReadingSupportCsvImporter().import_csv(
            self.HEADER
            + "NISA,ニーサ,少額投資非課税制度,制度,https://example.com/nisa\n"
            + "不完全,フカンゼン,,制度,\n"
        )

        self.assertFalse(result.is_success)
        self.assertEqual(result.errors[0].line_number, 3)
        self.assertIn("説明", result.errors[0].message)
        self.assertFalse(ReadingSupportEntry.objects.filter(surface="NISA").exists())


class ReadingSupportDraftServiceTests(TestCase):
    """GPT候補を下書きに保存し、承認後だけ辞書へ反映することを確認する。"""

    class FakeGenerator:
        model = "test-reading-support-model"

        def generate(self, source_text, source_url=""):
            return [
                {
                    "entry_type": "term",
                    "surface": "GX",
                    "reading": "ジーエックス",
                    "description": "脱炭素社会への移行に関する概念",
                    "category": "政策",
                    "source_url": source_url,
                    "needs_review": False,
                }
            ]

    class FakeFetcher:
        def fetch(self, url):
            return "Webページから取得した本文です。"

    def test_generated_candidates_are_not_registered_until_approved(self):
        """
        シナリオ:
        - 入力: Web情報から生成した、十分な項目を持つ候補。
        - 処理: 下書き作成後、管理者承認を付けて登録処理を行う。
        - 期待値: 下書き作成直後は辞書に存在せず、承認後だけ登録される。
        """
        service = ReadingSupportDraftService(
            fetcher=self.FakeFetcher(), generator=self.FakeGenerator()
        )
        draft = service.create_draft(
            source_url="https://example.com/gx",
            source_text="GXに関する一次資料です。",
        )

        candidate = draft.candidates.get()
        self.assertFalse(ReadingSupportEntry.objects.filter(surface="GX").exists())
        self.assertFalse(candidate.is_approved)

        candidate.is_approved = True
        candidate.save(update_fields=["is_approved", "updated_at"])
        result = service.register_approved_candidates(draft)

        self.assertEqual(result.registered, 1)
        self.assertFalse(result.errors)
        self.assertEqual(
            ReadingSupportEntry.objects.get(surface="GX").reading, "ジーエックス"
        )
        candidate.refresh_from_db()
        draft.refresh_from_db()
        self.assertTrue(candidate.is_registered)
        self.assertEqual(draft.status, draft.Status.IMPORTED)


class ReadingSupportAdminTests(TestCase):
    """管理画面からCSV取り込み画面へ到達できることを確認する。"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="reading-support-admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_csv_import_admin_view_imports_uploaded_file(self):
        """
        シナリオ:
        - 入力: 管理者が辞書CSV取り込み画面へCSVをアップロードする。
        - 処理: 管理画面のカスタム取り込みViewを実行する。
        - 期待値: 画面が成功し、辞書エントリが保存される。
        """
        response = self.client.post(
            reverse("admin:kokkai_readingsupportentry_csv_import"),
            {
                "file": SimpleUploadedFile(
                    "dictionary.csv",
                    (
                        "surface,reading,description,category,source_url\n"
                        "GX,ジーエックス,脱炭素社会への移行,政策,https://example.com/gx\n"
                    ).encode("utf-8"),
                    content_type="text/csv",
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(ReadingSupportEntry.objects.filter(surface="GX").exists())

    def test_custom_admin_views_require_model_permissions(self):
        """カスタム管理画面の直接アクセスでもモデル権限を要求する。"""
        staff_user = User.objects.create_user(
            username="reading-support-staff",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        csv_response = self.client.get(
            reverse("admin:kokkai_readingsupportentry_csv_import")
        )
        draft_response = self.client.get(
            reverse("admin:kokkai_readingsupportdraft_generate")
        )

        self.assertEqual(csv_response.status_code, 403)
        self.assertEqual(draft_response.status_code, 403)
