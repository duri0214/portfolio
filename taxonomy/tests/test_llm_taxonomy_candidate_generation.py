from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from taxonomy.domain.service.llm_taxonomy_candidate_generation import (
    LLMTaxonomyCandidateGenerationError,
    LLMTaxonomyCandidateGenerationService,
)
from taxonomy.models import (
    Classification,
    Family,
    Genus,
    Kingdom,
    LLMTaxonomyCandidateGenerationJob,
    Phylum,
    Species,
)


class LLMTaxonomyCandidateGenerationServiceTest(TestCase):
    def test_clean_candidate_data_extracts_fenced_json_and_truncates_fields(self):
        """
        シナリオ:
        - 入力: LLMがMarkdown fenced JSONと長すぎる外部IDを返す。
        - 処理: 候補データを保存前にクリーニングする。
        - 期待値: JSONを読み取り、DB上限に合わせて文字列を丸めること。
        """
        long_external_id = "x" * 300
        answer = f"""
        ```json
        [
          {{
            "kingdom_name": " 動物界 ",
            "kingdom_name_en": "Animalia",
            "phylum_name": "環形動物門",
            "phylum_name_en": "Annelida",
            "classification_name": "貧毛綱",
            "classification_name_en": "Oligochaeta",
            "family_name": "フトミミズ科",
            "family_name_en": "Megascolecidae",
            "genus_name": "フトミミズ属",
            "genus_name_en": "Pheretima",
            "species_name": "フトミミズ",
            "species_name_en": "Pheretima communissima",
            "breed_name": "フトミミズ",
            "breed_name_kana": "ふとみみず",
            "source_name": "Catalogue of Life",
            "source_url": "https://www.catalogueoflife.org/",
            "external_taxon_id": "{long_external_id}",
            "llm_note": "推定候補です。"
          }}
        ]
        ```
        """

        cleaned = LLMTaxonomyCandidateGenerationService._clean_candidate_data_list(
            answer
        )[0]

        self.assertEqual("動物界", cleaned["kingdom_name"])
        self.assertEqual("Catalogue of Life", cleaned["source_name"])
        self.assertEqual("https://www.catalogueoflife.org/", cleaned["source_url"])
        self.assertEqual(255, len(cleaned["external_taxon_id"]))
        self.assertIn("model=gpt-5-mini", cleaned["llm_note"])

    def test_clean_candidate_data_ignores_invalid_optional_source_url(self):
        """
        シナリオ:
        - 入力: LLMが任意項目の出典URLにURLとして保存できない文字列を返す。
        - 処理: 候補データを保存前にクリーニングする。
        - 期待値: 候補全体はエラーにせず、出典URLだけ空文字にすること。
        """
        answer = """
        [
          {
            "kingdom_name": "動物界",
            "kingdom_name_en": "Animalia",
            "phylum_name": "環形動物門",
            "phylum_name_en": "Annelida",
            "classification_name": "貧毛綱",
            "classification_name_en": "Oligochaeta",
            "family_name": "フトミミズ科",
            "family_name_en": "Megascolecidae",
            "genus_name": "フトミミズ属",
            "genus_name_en": "Pheretima",
            "species_name": "フトミミズ",
            "species_name_en": "Pheretima communissima",
            "breed_name": "フトミミズ",
            "breed_name_kana": "ふとみみず",
            "source_name": "Catalogue of Life",
            "source_url": "Catalogue of Life を参照",
            "external_taxon_id": "",
            "llm_note": ""
          }
        ]
        """

        cleaned = LLMTaxonomyCandidateGenerationService._clean_candidate_data_list(
            answer
        )[0]

        self.assertEqual("", cleaned["source_url"])

    def test_clean_candidate_data_adds_scheme_to_www_source_url(self):
        """
        シナリオ:
        - 入力: LLMがスキームなしのwwwから始まる出典URLを返す。
        - 処理: 候補データを保存前にクリーニングする。
        - 期待値: httpsスキームを補って保存可能なURLにすること。
        """
        answer = """
        [
          {
            "kingdom_name": "動物界",
            "kingdom_name_en": "Animalia",
            "phylum_name": "環形動物門",
            "phylum_name_en": "Annelida",
            "classification_name": "貧毛綱",
            "classification_name_en": "Oligochaeta",
            "family_name": "フトミミズ科",
            "family_name_en": "Megascolecidae",
            "genus_name": "フトミミズ属",
            "genus_name_en": "Pheretima",
            "species_name": "フトミミズ",
            "species_name_en": "Pheretima communissima",
            "breed_name": "フトミミズ",
            "breed_name_kana": "ふとみみず",
            "source_name": "Catalogue of Life",
            "source_url": "www.catalogueoflife.org/",
            "external_taxon_id": "",
            "llm_note": ""
          }
        ]
        """

        cleaned = LLMTaxonomyCandidateGenerationService._clean_candidate_data_list(
            answer
        )[0]

        self.assertEqual("https://www.catalogueoflife.org/", cleaned["source_url"])

    def test_clean_candidate_data_rejects_missing_required_fields(self):
        """
        シナリオ:
        - 入力: 必須分類階層が不足したLLM JSON。
        - 処理: 候補データを保存前にクリーニングする。
        - 期待値: 不足項目を示す例外が発生すること。
        """
        with self.assertRaises(LLMTaxonomyCandidateGenerationError):
            LLMTaxonomyCandidateGenerationService._clean_candidate_data_list(
                '[{"breed_name": "畑土系統"}]',
            )

    def test_clean_candidate_data_keeps_species_on_one_genus_path(self):
        """
        シナリオ:
        - 入力: LLMが同じ属に属する複数の種候補と、別属の候補を返す。
        - 処理: 候補データを保存前にクリーニングする。
        - 期待値: 1本目の属に属する候補だけが複数件採用されること。
        """
        answer = """
        [
          {
            "kingdom_name": "動物界",
            "kingdom_name_en": "Animalia",
            "phylum_name": "節足動物門",
            "phylum_name_en": "Arthropoda",
            "classification_name": "昆虫綱",
            "classification_name_en": "Insecta",
            "family_name": "ミツバチ科",
            "family_name_en": "Apidae",
            "genus_name": "Apis",
            "genus_name_en": "Apis",
            "species_name": "Apis cerana",
            "species_name_en": "Apis cerana",
            "breed_name": "Apis cerana",
            "breed_name_kana": "あじあみつばち",
            "source_name": "Catalogue of Life",
            "source_url": "https://www.catalogueoflife.org/",
            "external_taxon_id": "",
            "llm_note": ""
          },
          {
            "kingdom_name": "動物界",
            "kingdom_name_en": "Animalia",
            "phylum_name": "節足動物門",
            "phylum_name_en": "Arthropoda",
            "classification_name": "昆虫綱",
            "classification_name_en": "Insecta",
            "family_name": "ミツバチ科",
            "family_name_en": "Apidae",
            "genus_name": "Apis",
            "genus_name_en": "Apis",
            "species_name": "Apis dorsata",
            "species_name_en": "Apis dorsata",
            "breed_name": "Apis dorsata",
            "breed_name_kana": "おおみつばち",
            "source_name": "Catalogue of Life",
            "source_url": "https://www.catalogueoflife.org/",
            "external_taxon_id": "",
            "llm_note": ""
          },
          {
            "kingdom_name": "動物界",
            "kingdom_name_en": "Animalia",
            "phylum_name": "節足動物門",
            "phylum_name_en": "Arthropoda",
            "classification_name": "昆虫綱",
            "classification_name_en": "Insecta",
            "family_name": "ミツバチ科",
            "family_name_en": "Apidae",
            "genus_name": "Apis",
            "genus_name_en": "Apis",
            "species_name": "Apis mellifera",
            "species_name_en": "Apis mellifera",
            "breed_name": "Apis mellifera",
            "breed_name_kana": "せいようみつばち",
            "source_name": "Catalogue of Life",
            "source_url": "https://www.catalogueoflife.org/",
            "external_taxon_id": "",
            "llm_note": ""
          },
          {
            "kingdom_name": "動物界",
            "phylum_name": "脊索動物門",
            "classification_name": "哺乳綱",
            "family_name": "ウシ科",
            "genus_name": "Bos",
            "species_name": "Bos taurus",
            "breed_name": "黒毛和種"
          }
        ]
        """

        cleaned = LLMTaxonomyCandidateGenerationService._clean_candidate_data_list(
            answer
        )

        self.assertEqual(3, len(cleaned))
        self.assertEqual("Apis cerana", cleaned[0]["breed_name"])
        self.assertEqual("Apis dorsata", cleaned[1]["species_name"])
        self.assertEqual("Apis mellifera", cleaned[2]["species_name"])

    def test_clean_candidate_data_rejects_duplicate_species_names(self):
        """
        シナリオ:
        - 入力: LLMが同じ種名の候補を複数返す。
        - 処理: 候補データを保存前にクリーニングする。
        - 期待値: 種名重複として例外が発生すること。
        """
        answer = """
        [
          {
            "kingdom_name": "動物界",
            "phylum_name": "節足動物門",
            "classification_name": "昆虫綱",
            "family_name": "ミツバチ科",
            "genus_name": "Apis",
            "species_name": "Apis cerana",
            "breed_name": "Apis cerana"
          },
          {
            "kingdom_name": "動物界",
            "phylum_name": "節足動物門",
            "classification_name": "昆虫綱",
            "family_name": "ミツバチ科",
            "genus_name": "Apis",
            "species_name": "Apis cerana",
            "breed_name": "Apis cerana"
          }
        ]
        """

        with self.assertRaisesMessage(
            LLMTaxonomyCandidateGenerationError,
            "LLM生成結果の種名が重複しています。",
        ):
            LLMTaxonomyCandidateGenerationService._clean_candidate_data_list(answer)

    def test_clean_candidate_data_rejects_species_caption_mismatch(self):
        """
        シナリオ:
        - 入力: LLMが種名と画面キャプションの異なる候補を返す。
        - 処理: 候補データを保存前にクリーニングする。
        - 期待値: 種名とキャプションの不一致として例外が発生すること。
        """
        answer = """
        [
          {
            "kingdom_name": "動物界",
            "phylum_name": "節足動物門",
            "classification_name": "昆虫綱",
            "family_name": "ミツバチ科",
            "genus_name": "Apis",
            "species_name": "Apis cerana",
            "breed_name": "ニホンミツバチ"
          }
        ]
        """

        with self.assertRaisesMessage(
            LLMTaxonomyCandidateGenerationError,
            "LLM生成結果の種名とキャプションが一致していません。",
        ):
            LLMTaxonomyCandidateGenerationService._clean_candidate_data_list(answer)

    def test_clean_target_names_deduplicates_target_list(self):
        """
        シナリオ:
        - 入力: LLMが重複や空白を含む生成対象名JSONを返す。
        - 処理: 対象名リストを保存前にクリーニングする。
        - 期待値: 空白を除去し、重複を除いた対象名だけが返ること。
        """
        target_names = LLMTaxonomyCandidateGenerationService._clean_target_names(
            '[" Apis cerana ", "Apis cerana", "", "Apis dorsata"]'
        )

        self.assertEqual(["Apis cerana", "Apis dorsata"], target_names)

    def test_process_job_first_step_prepares_target_names(self):
        """
        シナリオ:
        - 入力: 準備中の生成ジョブと、mockされた生成対象名。
        - 処理: ジョブを1ステップ進める。
        - 期待値: ジョブが生成中になり、対象名と総数が保存されること。
        """
        job = LLMTaxonomyCandidateGenerationJob.objects.create()

        with (
            patch(
                "taxonomy.domain.service.llm_taxonomy_candidate_generation."
                "LLMTaxonomyCandidateGenerationService._generate_target_names",
                return_value=["Apis cerana", "Apis dorsata"],
            ),
            patch("taxonomy.domain.service.llm_taxonomy_candidate_generation.logger"),
        ):
            updated_job = LLMTaxonomyCandidateGenerationService.process_next_job_step(
                job
            )

        updated_job.refresh_from_db()
        self.assertEqual(
            updated_job.status,
            LLMTaxonomyCandidateGenerationJob.JobStatus.RUNNING,
        )
        self.assertEqual(updated_job.current_step, "生成対象リスト作成")
        self.assertEqual(updated_job.current_target, "Apis cerana")
        self.assertEqual(updated_job.total_count, 2)
        self.assertEqual(updated_job.target_names, ["Apis cerana", "Apis dorsata"])

    def test_start_job_logs_initial_state(self):
        """
        シナリオ:
        - 入力: ジョブ開始ユーザー。
        - 処理: LLM分類候補生成ジョブを開始する。
        - 期待値: Job ID、作成者、初期状態がログに渡されること。
        """
        user = get_user_model().objects.create_user(
            username="taxonomy_job_logger",
            email="taxonomy_job_logger@example.com",
            password="password",
        )

        with patch(
            "taxonomy.domain.service.llm_taxonomy_candidate_generation.logger"
        ) as mock_logger:
            job = LLMTaxonomyCandidateGenerationService.start_job(user)

        log_kwargs = mock_logger.info.call_args.kwargs
        self.assertEqual(
            "LLM分類候補生成ジョブを開始しました。",
            mock_logger.info.call_args.args[0],
        )
        self.assertEqual(log_kwargs["extra"]["job_id"], job.pk)
        self.assertEqual(log_kwargs["extra"]["created_by_id"], user.pk)
        self.assertEqual(log_kwargs["extra"]["created_by_username"], user.username)
        self.assertEqual(
            log_kwargs["extra"]["status"],
            LLMTaxonomyCandidateGenerationJob.JobStatus.PENDING,
        )

    def test_process_job_first_step_logs_target_summary(self):
        """
        シナリオ:
        - 入力: 準備中の生成ジョブと、mockされた生成対象名。
        - 処理: ジョブの対象リスト作成ステップを進める。
        - 期待値: 対象件数と先頭対象名がログに渡されること。
        """
        job = LLMTaxonomyCandidateGenerationJob.objects.create()

        with (
            patch(
                "taxonomy.domain.service.llm_taxonomy_candidate_generation."
                "LLMTaxonomyCandidateGenerationService._generate_target_names",
                return_value=["Apis cerana", "Apis dorsata"],
            ),
            patch(
                "taxonomy.domain.service.llm_taxonomy_candidate_generation.logger"
            ) as mock_logger,
        ):
            updated_job = LLMTaxonomyCandidateGenerationService.process_next_job_step(
                job
            )

        log_kwargs = mock_logger.info.call_args.kwargs
        self.assertEqual(
            "LLM分類候補生成ジョブの対象リスト作成が完了しました。",
            mock_logger.info.call_args.args[0],
        )
        self.assertEqual(log_kwargs["extra"]["job_id"], updated_job.pk)
        self.assertEqual(log_kwargs["extra"]["total_count"], 2)
        self.assertEqual(log_kwargs["extra"]["first_target"], "Apis cerana")

    def test_process_job_detail_step_logs_success_and_completion(self):
        """
        シナリオ:
        - 入力: 対象名1件を持つ生成中ジョブと、mockされた候補データ。
        - 処理: ジョブの詳細生成ステップを進める。
        - 期待値: 詳細生成開始、成功、ジョブ完了のログが渡されること。
        """
        job = LLMTaxonomyCandidateGenerationJob.objects.create(
            status=LLMTaxonomyCandidateGenerationJob.JobStatus.RUNNING,
            target_names=["Apis cerana"],
            total_count=1,
        )

        with (
            patch(
                "taxonomy.domain.service.llm_taxonomy_candidate_generation."
                "LLMTaxonomyCandidateGenerationService._generate_candidate_detail",
                return_value=[self._candidate_data({"breed_name": "Apis cerana"})],
            ),
            patch(
                "taxonomy.domain.service.llm_taxonomy_candidate_generation.logger"
            ) as mock_logger,
        ):
            updated_job = LLMTaxonomyCandidateGenerationService.process_next_job_step(
                job
            )

        messages = [call.args[0] for call in mock_logger.info.call_args_list]
        self.assertIn(
            "LLM分類候補生成ジョブの候補詳細生成を開始しました。",
            messages,
        )
        self.assertIn(
            "LLM分類候補生成ジョブの候補詳細生成が完了しました。",
            messages,
        )
        self.assertIn("LLM分類候補生成ジョブが完了しました。", messages)
        completion_log = mock_logger.info.call_args_list[-1]
        self.assertEqual(completion_log.kwargs["extra"]["job_id"], updated_job.pk)
        self.assertEqual(completion_log.kwargs["extra"]["processed_count"], 1)
        self.assertEqual(completion_log.kwargs["extra"]["success_count"], 1)
        self.assertEqual(completion_log.kwargs["extra"]["failed_count"], 0)
        self.assertTrue(completion_log.kwargs["extra"]["has_preview_url"])

    def test_process_job_detail_step_logs_failure(self):
        """
        シナリオ:
        - 入力: 詳細生成がエラーになる生成中ジョブ。
        - 処理: ジョブの詳細生成ステップを進める。
        - 期待値: 対象名、処理位置、エラー内容がwarningログに渡されること。
        """
        job = LLMTaxonomyCandidateGenerationJob.objects.create(
            status=LLMTaxonomyCandidateGenerationJob.JobStatus.RUNNING,
            target_names=["失敗候補"],
            total_count=1,
        )

        with (
            patch(
                "taxonomy.domain.service.llm_taxonomy_candidate_generation."
                "LLMTaxonomyCandidateGenerationService._generate_candidate_detail",
                side_effect=LLMTaxonomyCandidateGenerationError(
                    "保存できる候補がありません。"
                ),
            ),
            patch(
                "taxonomy.domain.service.llm_taxonomy_candidate_generation.logger"
            ) as mock_logger,
        ):
            LLMTaxonomyCandidateGenerationService.process_next_job_step(job)

        log_kwargs = mock_logger.warning.call_args.kwargs
        self.assertEqual(
            "LLM分類候補生成ジョブの候補詳細生成が失敗しました。",
            mock_logger.warning.call_args.args[0],
        )
        self.assertEqual(log_kwargs["extra"]["job_id"], job.pk)
        self.assertEqual(log_kwargs["extra"]["position"], 1)
        self.assertEqual(log_kwargs["extra"]["target_name"], "失敗候補")
        self.assertEqual(
            log_kwargs["extra"]["error_message"],
            "保存できる候補がありません。",
        )

    def test_user_prompt_includes_existing_species_hierarchy(self):
        """
        シナリオ:
        - 入力: 既存taxonomyに動物界からニワトリまでの階層が登録済み。
        - 処理: LLM生成用のユーザープロンプトを作る。
        - 期待値: 既存ノードを再利用して枝を伸ばせるよう、種までの階層が含まれること。
        """
        kingdom = Kingdom.objects.create(name="動物界", name_en="Animalia")
        phylum = Phylum.objects.create(
            name="脊索動物門",
            name_en="Chordata",
            kingdom=kingdom,
        )
        classification = Classification.objects.create(
            name="鳥綱",
            name_en="Aves",
            phylum=phylum,
        )
        family = Family.objects.create(
            name="キジ科",
            name_en="Phasianidae",
            classification=classification,
        )
        genus = Genus.objects.create(
            name="ヤケイ属",
            name_en="Gallus",
            family=family,
        )
        Species.objects.create(
            name="ニワトリ",
            name_en="Gallus gallus domesticus",
            genus=genus,
        )

        prompt = LLMTaxonomyCandidateGenerationService._user_prompt()

        self.assertIn(
            "動物界 > 脊索動物門 > 鳥綱 > キジ科 > ヤケイ属 > ニワトリ",
            prompt,
        )
        self.assertIn("界、門、綱、科、属はJSON配列内の全要素で同じ値", prompt)
        self.assertIn("species_nameはJSON配列内で全件異なる値", prompt)
        self.assertIn("breed_nameにはspecies_nameと同じ値", prompt)
        self.assertIn("Betta splendens", prompt)
        self.assertIn("Siamese fighting fish", prompt)
        self.assertIn("llm_noteに両者が同じ種を指す根拠", prompt)
        self.assertIn("同じ種の根拠を書けない場合", prompt)
        self.assertIn("アジアミツバチならspecies_nameはアジアミツバチ", prompt)
        self.assertIn("Apis cerana koreana", prompt)
        self.assertIn("地域名から作った未確認の亜種名・系統名は返さない", prompt)

    def _candidate_data(self, overrides=None):
        data = {
            "kingdom_name": "動物界",
            "kingdom_name_en": "Animalia",
            "phylum_name": "節足動物門",
            "phylum_name_en": "Arthropoda",
            "classification_name": "昆虫綱",
            "classification_name_en": "Insecta",
            "family_name": "ミツバチ科",
            "family_name_en": "Apidae",
            "genus_name": "Apis",
            "genus_name_en": "Apis",
            "species_name": "Apis cerana",
            "species_name_en": "Apis cerana",
            "breed_name": "Apis cerana",
            "breed_name_kana": "あじあみつばち",
            "source_name": "Catalogue of Life",
            "source_url": "https://www.catalogueoflife.org/",
            "external_taxon_id": "",
            "llm_note": "LLMが生成した候補。",
        }
        if overrides:
            data.update(overrides)
        return data
