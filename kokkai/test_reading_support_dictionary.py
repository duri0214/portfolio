from django.core.exceptions import ValidationError
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from kokkai.domain.service.reading_support import ReadingSupportService
from kokkai.domain.service.reading_support_draft import ReadingSupportDraftService
from kokkai.domain.service.reading_support_import import ReadingSupportCsvImporter
from kokkai.models import (
    ReadingSupportDraft,
    ReadingSupportDraftCandidate,
    ReadingSupportEntry,
)


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


class ReadingSupportManagementViewTests(TestCase):
    """KOKKAI内の辞書管理画面と管理者権限を確認する。"""

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

    def test_index_keeps_word_management_button_visible_but_disabled_for_guests(self):
        """
        シナリオ:
        - 入力: 未ログインの利用者がKOKKAI会議録一覧を表示する。
        - 処理: ワード管理への導線を確認する。
        - 期待値: ボタンは非表示にならずdisabledで表示され、管理者権限が必要だと分かる。
        """
        response = self.client.get(reverse("kokkai:index"))

        self.assertContains(
            response,
            '<button type="button" class="btn btn-outline-secondary" disabled>ワード管理</button>',
            html=False,
        )
        self.assertContains(response, "ワード管理を利用するには管理者権限が必要です。")
        self.assertNotContains(response, "CSVから取り込む")
        self.assertNotContains(response, "Webから取り込む")
        self.assertNotContains(response, "Web取込候補")
        self.assertNotContains(response, "/admin/")

    def test_index_links_single_word_management_button_for_superuser(self):
        """
        シナリオ:
        - 入力: スーパーユーザーがKOKKAI会議録一覧を表示する。
        - 処理: ワード管理への導線を確認する。
        - 期待値: ワード管理ボタン1つだけがKOKKAI内の管理モードへリンクする。
        """
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("kokkai:index"))

        self.assertContains(
            response,
            f'href="{reverse("kokkai:reading_support_management")}"',
            count=1,
        )
        self.assertContains(response, "ワード管理")
        self.assertNotContains(response, "CSVから取り込む")
        self.assertNotContains(response, "Webから取り込む")
        self.assertNotContains(response, "Web取込候補")

    def test_management_pages_require_a_superuser(self):
        """
        シナリオ:
        - 入力: 通常ユーザーがKOKKAI内の辞書管理画面へ直接アクセスする。
        - 処理: 辞書一覧、CSV取り込み、候補一覧をGETする。
        - 期待値: いずれも403を返し、管理者権限なしで機能を実行できない。
        """
        self.client.force_login(self.regular_user)

        for view_name in (
            "kokkai:reading_support_management",
            "kokkai:reading_support_csv_import",
            "kokkai:reading_support_draft_list",
            "kokkai:reading_support_draft_generate",
        ):
            response = self.client.get(reverse(view_name))
            self.assertEqual(response.status_code, 403)

    def test_management_pages_render_inside_the_kokkai_app(self):
        """
        シナリオ:
        - 入力: スーパーユーザーがKOKKAI内の辞書管理関連画面を表示する。
        - 処理: 辞書一覧、CSV取り込み、候補一覧、候補作成を順にGETする。
        - 期待値: すべての画面がKOKKAIの共通レイアウトで200を返す。
        """
        self.client.force_login(self.admin_user)

        for view_name in (
            "kokkai:reading_support_management",
            "kokkai:reading_support_csv_import",
            "kokkai:reading_support_draft_list",
            "kokkai:reading_support_draft_generate",
        ):
            response = self.client.get(reverse(view_name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "会議録一覧")

        management_response = self.client.get(
            reverse("kokkai:reading_support_management")
        )
        self.assertContains(management_response, "管理モード")
        self.assertContains(management_response, "辞書ビューア")
        self.assertContains(management_response, "CSVから取り込む")
        self.assertContains(management_response, "Webから取り込む")
        self.assertContains(management_response, "Web取込候補を確認")

    def test_entry_form_creates_a_dictionary_entry(self):
        """
        シナリオ:
        - 入力: 管理者がKOKKAI内の辞書エントリ追加画面へ用語情報を入力する。
        - 処理: 辞書エントリ追加フォームを送信する。
        - 期待値: 辞書一覧へ戻り、入力した用語が有効な状態で保存される。
        """
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("kokkai:reading_support_entry_create"),
            {
                "entry_type": "term",
                "surface": "確認用語",
                "reading": "カクニンヨウゴ",
                "description": "確認用の説明",
                "category": "確認",
                "source_url": "https://example.com/check",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("kokkai:reading_support_management"))
        entry = ReadingSupportEntry.objects.get(surface="確認用語")
        self.assertTrue(entry.is_active)

    @patch("kokkai.views.ReadingSupportDraftService")
    def test_draft_generation_view_redirects_to_the_created_draft(self, service_class):
        """
        シナリオ:
        - 入力: 管理者がKOKKAI内の候補作成画面へ本文を入力する。
        - 処理: GPT候補作成サービスを呼び出す。
        - 期待値: 作成された下書きの確認画面へ遷移する。
        """
        self.client.force_login(self.admin_user)
        draft = ReadingSupportDraft.objects.create(source_text="確認用本文")
        service_class.return_value.create_draft.return_value = draft

        response = self.client.post(
            reverse("kokkai:reading_support_draft_generate"),
            {"source_text": "確認用本文"},
        )

        self.assertRedirects(
            response,
            reverse("kokkai:reading_support_draft_detail", args=[draft.pk]),
        )
        service_class.return_value.create_draft.assert_called_once()

    def test_draft_detail_registers_approved_candidates(self):
        """
        シナリオ:
        - 入力: 管理者が候補の内容を確認し、登録承認を付けた下書き。
        - 処理: 候補確認画面から承認済み候補の登録を実行する。
        - 期待値: 候補が辞書へ登録され、下書きと候補が登録済みになる。
        """
        self.client.force_login(self.admin_user)
        draft = ReadingSupportDraft.objects.create(source_text="GXの一次資料")
        candidate = ReadingSupportDraftCandidate.objects.create(
            draft=draft,
            entry_type="term",
            surface="GX確認",
            reading="ジーエックスカクニン",
            description="脱炭素社会への移行",
            category="政策",
            source_url="https://example.com/gx-check",
        )

        response = self.client.post(
            reverse("kokkai:reading_support_draft_detail", args=[draft.pk]),
            {
                "candidates-TOTAL_FORMS": "1",
                "candidates-INITIAL_FORMS": "1",
                "candidates-MIN_NUM_FORMS": "0",
                "candidates-MAX_NUM_FORMS": "1000",
                "candidates-0-id": str(candidate.pk),
                "candidates-0-entry_type": "term",
                "candidates-0-surface": "GX確認",
                "candidates-0-reading": "ジーエックスカクニン",
                "candidates-0-description": "脱炭素社会への移行",
                "candidates-0-category": "政策",
                "candidates-0-source_url": "https://example.com/gx-check",
                "candidates-0-needs_review": "",
                "candidates-0-is_approved": "on",
                "candidates-0-review_note": "確認済み",
                "action": "register_candidates",
            },
        )

        self.assertRedirects(
            response,
            reverse("kokkai:reading_support_draft_detail", args=[draft.pk]),
        )
        self.assertTrue(ReadingSupportEntry.objects.filter(surface="GX確認").exists())
        candidate.refresh_from_db()
        draft.refresh_from_db()
        self.assertTrue(candidate.is_registered)
        self.assertEqual(draft.status, draft.Status.IMPORTED)

    def test_csv_import_view_imports_uploaded_file(self):
        """
        シナリオ:
        - 入力: 管理者がKOKKAI内のCSV取り込み画面へ辞書CSVをアップロードする。
        - 処理: CSV取り込みフォームを送信する。
        - 期待値: KOKKAIの辞書一覧へリダイレクトし、辞書エントリが保存される。
        """
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("kokkai:reading_support_csv_import"),
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

        self.assertRedirects(response, reverse("kokkai:reading_support_management"))
        self.assertTrue(ReadingSupportEntry.objects.filter(surface="GX").exists())
