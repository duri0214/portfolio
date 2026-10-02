import csv
import io
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from kokkai.domain.service.reading_support import ReadingSupportService
from kokkai.domain.service.reading_support_candidates import (
    CandidateGenerationError,
    ReadingSupportCandidateService,
)
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


class ReadingSupportCandidateServiceTests(TestCase):
    """候補CSVの元行保持、重複除去、失敗時の扱いを確認する。"""

    HEADER = "word,reading,description,source_url\n"

    def test_generates_distinct_variant_and_preserves_original_rows(self):
        """
        シナリオ:
        - 入力: 子どもとFOIPの元行、同義候補と表記差だけの候補。
        - 処理: 行ごとに候補を生成し、既存取り込み形式のCSVを作る。
        - 期待値: 元行を保ち、こどもだけ追加し、候補の出典は空欄になる。
        """
        generator = Mock()
        generator.generate.side_effect = [
            ["こども", "子ども", "FOIP"],
            ["ＦＯＩＰ", "foip"],
        ]
        service = ReadingSupportCandidateService(generator=generator)

        result = service.generate_csv(
            self.HEADER
            + "子ども,こども,子供の別表記,https://example.com/child\n"
            + "FOIP,フォイップ,外交構想,\n"
        )
        rows = list(csv.DictReader(io.StringIO(result.to_csv())))

        self.assertFalse(result.errors)
        self.assertEqual([row["word"] for row in rows], ["子ども", "こども", "FOIP"])
        self.assertEqual(rows[0]["source_url"], "https://example.com/child")
        self.assertEqual(rows[1]["reading"], "こども")
        self.assertEqual(rows[1]["description"], "子供の別表記")
        self.assertEqual(rows[1]["source_url"], "")
        self.assertEqual(result.warnings[0].line_number, 3)
        self.assertTrue(
            ReadingSupportCsvImporter().import_csv(result.to_csv()).is_success
        )

    def test_failure_keeps_original_and_reports_line(self):
        """
        シナリオ:
        - 入力: GPTが生成に失敗する有効な辞書行。
        - 処理: 候補CSVを作る。
        - 期待値: 元行だけを出力し、行番号と理由を確認できる。
        """
        generator = Mock()
        generator.generate.side_effect = CandidateGenerationError(
            "APIが利用できません。"
        )

        result = ReadingSupportCandidateService(generator).generate_csv(
            self.HEADER + "子ども,こども,子供の別表記,\n"
        )

        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].word, "子ども")
        self.assertTrue(result.generation_failed)
        self.assertEqual(result.warnings[0].line_number, 2)
        self.assertIn("APIが利用できません", result.warnings[0].message)

    def test_no_candidate_keeps_original_and_explains_result(self):
        """
        シナリオ:
        - 入力: GPTが別表記なしと返す辞書行。
        - 処理: 候補CSVを作る。
        - 期待値: 元行を残し、候補がない理由を表示する。
        """
        generator = Mock()
        generator.generate.return_value = []

        result = ReadingSupportCandidateService(generator).generate_csv(
            self.HEADER + "FOIP,フォイップ,外交構想,\n"
        )

        self.assertEqual([row.word for row in result.rows], ["FOIP"])
        self.assertIn("候補は見つかりません", result.warnings[0].message)

    def test_invalid_csv_does_not_call_gpt(self):
        """
        シナリオ:
        - 入力: 読みが空の行と正規化後に重複する行。
        - 処理: 候補生成前に入力CSVを検証する。
        - 期待値: 行ごとのエラーを返し、GPTを呼ばない。
        """
        generator = Mock()

        result = ReadingSupportCandidateService(generator).generate_csv(
            self.HEADER + "FOIP,,説明,\nＦＯＩＰ,ふぉいっぷ,説明,\n"
        )

        self.assertEqual([error.line_number for error in result.errors], [2, 3])
        generator.generate.assert_not_called()


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
        - 処理: 辞書一覧とCSVテンプレートを開く。
        - 期待値: どちらもHTTP 403になる。
        """
        self.client.force_login(self.regular_user)
        for view_name in (
            "kokkai:reading_support_management",
            "kokkai:reading_support_csv_template",
        ):
            response = self.client.get(reverse(view_name))
            self.assertEqual(response.status_code, 403)

    def test_csv_import_form_is_visible_but_disabled_without_superuser(self):
        """
        シナリオ:
        - 入力: 未ログイン利用者または一般ユーザーによるCSV取り込み画面の表示。
        - 処理: CSV取り込み画面を開く。
        - 期待値: GPT候補生成のチェックボックスと実行ボタンが無効になり、トークン利用の説明を確認できる。
        """
        for user in (None, self.regular_user):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)

            response = self.client.get(reverse("kokkai:reading_support_csv_import"))
            index = self.client.get(reverse("kokkai:index"))

            self.assertEqual(response.status_code, 200)
            self.assertNotContains(
                index,
                f'href="{reverse("kokkai:reading_support_csv_import")}"',
            )
            self.assertContains(
                response, 'name="file" class="form-control" required disabled'
            )
            self.assertContains(
                response,
                'name="generate_candidates" class="form-check-input" disabled',
            )
            self.assertContains(
                response, "トークンを消費し、API利用料金が発生する場合があります"
            )
            self.assertContains(
                response,
                'id="csv-submit" type="submit" class="btn btn-primary" disabled',
            )
            self.assertContains(
                response,
                'type="button" class="btn btn-outline-secondary" disabled>CSVテンプレート',
            )
            self.assertNotContains(
                response,
                f'href="{reverse("kokkai:reading_support_management")}"',
            )

    def test_csv_import_form_is_enabled_for_superuser(self):
        """
        シナリオ:
        - 入力: スーパーユーザーによるCSV取り込み画面の表示。
        - 処理: CSV取り込み画面を開く。
        - 期待値: GPT候補生成のチェックボックスと実行ボタンを操作できる。
        """
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("kokkai:reading_support_csv_import"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="file" class="form-control" required')
        self.assertContains(
            response, 'name="generate_candidates" class="form-check-input"'
        )
        self.assertNotContains(
            response,
            'name="generate_candidates" class="form-check-input" disabled',
        )
        self.assertNotContains(
            response,
            'id="csv-submit" type="submit" class="btn btn-primary" disabled',
        )

    def test_csv_import_post_is_rejected_without_superuser(self):
        """
        シナリオ:
        - 入力: 未ログイン利用者と一般ユーザーによるCSV取り込み・候補CSVダウンロードPOST。
        - 処理: それぞれのPOSTを要求する。
        - 期待値: サーバー側でHTTP 403を返し、権限を迂回できない。
        """
        for user in (None, self.regular_user):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            for payload in ({"generate_candidates": "on"}, {"candidate_csv": ""}):
                response = self.client.post(
                    reverse("kokkai:reading_support_csv_import"), payload
                )
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

    def test_management_view_reuses_kokkai_page_size_options(self):
        """
        シナリオ:
        - 入力: 31件の辞書項目とスーパーユーザー。
        - 処理: 辞書一覧の1ページ目、2ページ目、60件表示を開く。
        - 期待値: 会議録一覧と同じ30、60、120件の選択肢でページングされる。
        """
        ReadingSupportEntry.objects.all().delete()
        ReadingSupportEntry.objects.bulk_create(
            [
                ReadingSupportEntry(
                    word=f"ページング単語{number:02d}",
                    normalized_word=f"ページング単語{number:02d}",
                    reading=f"ぺーじんぐたんご{number:02d}",
                    description="ページング確認用の説明",
                )
                for number in range(31)
            ]
        )
        self.client.force_login(self.admin_user)

        first_page = self.client.get(reverse("kokkai:reading_support_management"))
        second_page = self.client.get(
            reverse("kokkai:reading_support_management"), {"page": "2"}
        )
        sixty_page = self.client.get(
            reverse("kokkai:reading_support_management"), {"page_size": "60"}
        )

        self.assertContains(
            first_page,
            'class="btn btn-primary">CSVから取り込む</a>',
        )
        self.assertContains(
            first_page,
            'class="btn btn-outline-secondary mt-4">会議録一覧へ戻る</a>',
        )
        self.assertContains(first_page, "出典")
        self.assertEqual(first_page.context["page_size_options"], (30, 60, 120))
        self.assertEqual(first_page.context["page_size"], 30)
        self.assertEqual(first_page.context["paginator"].per_page, 30)
        self.assertEqual(first_page.context["paginator"].count, 31)
        self.assertEqual(len(first_page.context["entries"]), 30)
        self.assertContains(first_page, "1-30件 / 全31件")
        self.assertContains(first_page, "?page_size=30&page=2")
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertEqual(len(second_page.context["entries"]), 1)
        self.assertContains(second_page, "31-31件 / 全31件")
        self.assertEqual(sixty_page.context["paginator"].per_page, 60)

    def test_csv_template_download_has_sample_data(self):
        """
        シナリオ:
        - 入力: スーパーユーザーによるCSVテンプレートのダウンロード要求。
        - 処理: テンプレートURLを開く。
        - 期待値: 初期投入値と新規追加例を含むUTF-8 BOM付きのCSVがダウンロードされる。
        """
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("kokkai:reading_support_csv_template"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(
            'attachment; filename="reading-support-dictionary-template.csv"',
            response["Content-Disposition"],
        )
        self.assertEqual(
            response.content.decode("utf-8-sig"),
            (
                "word,reading,description,source_url\r\n"
                "FOIP,フォイップ,Free and Open Indo-Pacific（自由で開かれたインド太平洋）の略称で、法の支配に基づく自由で開かれた地域の実現を目指す外交上の概念です。,https://www.meti.go.jp/policy/external_economy/trade/foip/index.html\r\n"
                "お諮り,おはかり,読み仮名を補正するための登録語です。,\r\n"
                "NISA,ニーサ,少額投資非課税制度です。,https://example.com/nisa\r\n"
            ),
        )

    def test_csv_import_view_explains_word_based_overwrite_rule(self):
        """
        シナリオ:
        - 入力: スーパーユーザーによるCSV取り込み画面へのアクセス。
        - 処理: 取り込みルールの説明を表示する。
        - 期待値: wordだけで照合し、上書き範囲とCSV内重複時の扱いを確認できる。
        """
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("kokkai:reading_support_csv_import"))

        self.assertContains(response, "CSVの形式")
        self.assertContains(response, "取り込み時の扱い")
        self.assertContains(response, "CSVファイルを選択して取り込む")
        self.assertContains(response, "<code>word</code>（単語）")
        self.assertContains(response, "<code>reading</code>（読み）")
        self.assertContains(response, "<code>description</code>（説明）")
        self.assertContains(response, "<code>source_url</code>（出典）")
        self.assertContains(response, "wordだけ")
        self.assertContains(
            response, "reading、description、source_urlをCSVの値で上書き"
        )
        self.assertContains(response, "同じCSV内に同じwordが複数ある場合はエラー")

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

    @patch(
        "kokkai.domain.service.reading_support_candidates.OpenAIVariantGenerator.generate"
    )
    def test_csv_import_view_imports_uploaded_file(self, generate):
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
        generate.assert_not_called()

    @patch(
        "kokkai.domain.service.reading_support_candidates.OpenAIVariantGenerator.generate",
        return_value=["こども"],
    )
    def test_candidate_mode_previews_and_downloads_without_db_changes(self, generate):
        """
        シナリオ:
        - 入力: スーパーユーザー、子どものCSV、候補生成チェック。
        - 処理: プレビューを表示し、候補CSVをダウンロードする。
        - 期待値: 元行と候補行を得て、辞書DBを変更しない。
        """
        self.client.force_login(self.admin_user)
        before = list(ReadingSupportEntry.objects.values_list("pk", flat=True))
        response = self.client.post(
            reverse("kokkai:reading_support_csv_import"),
            {
                "file": SimpleUploadedFile(
                    "dictionary.csv",
                    (
                        "word,reading,description,source_url\n"
                        "子ども,こども,子供の別表記,https://example.com/child\n"
                    ).encode("utf-8"),
                ),
                "generate_candidates": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "辞書を変更していません")
        self.assertEqual(len(response.context["candidate_result"].rows), 2)
        download = self.client.post(
            reverse("kokkai:reading_support_csv_import"),
            {"candidate_csv": response.context["candidate_csv"]},
        )
        downloaded = list(
            csv.DictReader(io.StringIO(download.content.decode("utf-8-sig")))
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual([row["word"] for row in downloaded], ["子ども", "こども"])
        self.assertEqual(downloaded[1]["source_url"], "")
        self.assertEqual(
            before, list(ReadingSupportEntry.objects.values_list("pk", flat=True))
        )
        generate.assert_called_once()

    def test_candidate_mode_rejects_invalid_csv_without_db_changes(self):
        """
        シナリオ:
        - 入力: 説明が空のCSVと候補生成チェック。
        - 処理: 候補生成を要求する。
        - 期待値: HTTP 400と行の理由を返し、辞書DBを変更しない。
        """
        self.client.force_login(self.admin_user)
        before = ReadingSupportEntry.objects.count()

        response = self.client.post(
            reverse("kokkai:reading_support_csv_import"),
            {
                "file": SimpleUploadedFile(
                    "dictionary.csv",
                    "word,reading,description,source_url\n子ども,こども,,\n".encode(
                        "utf-8"
                    ),
                ),
                "generate_candidates": "on",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "説明を入力してください", status_code=400)
        self.assertEqual(ReadingSupportEntry.objects.count(), before)

    @patch(
        "kokkai.domain.service.reading_support_candidates.OpenAIVariantGenerator.generate",
        side_effect=CandidateGenerationError("GPTが利用できません。"),
    )
    def test_candidate_generation_failure_returns_original_csv(self, generate):
        """
        シナリオ:
        - 入力: GPTが失敗する有効なCSVと候補生成チェック。
        - 処理: 失敗理由を表示し、元行だけのCSVを取得する。
        - 期待値: HTTP 502で理由を示し、DB変更なしで元行をダウンロードできる。
        """
        self.client.force_login(self.admin_user)
        before = ReadingSupportEntry.objects.count()
        response = self.client.post(
            reverse("kokkai:reading_support_csv_import"),
            {
                "file": SimpleUploadedFile(
                    "dictionary.csv",
                    "word,reading,description,source_url\n子ども,こども,子供の別表記,\n".encode(
                        "utf-8"
                    ),
                ),
                "generate_candidates": "on",
            },
        )

        self.assertContains(response, "GPTが利用できません", status_code=502)
        download = self.client.post(
            reverse("kokkai:reading_support_csv_import"),
            {"candidate_csv": response.context["candidate_csv"]},
        )
        rows = list(csv.DictReader(io.StringIO(download.content.decode("utf-8-sig"))))
        self.assertEqual([row["word"] for row in rows], ["子ども"])
        self.assertEqual(ReadingSupportEntry.objects.count(), before)
        generate.assert_called_once()
