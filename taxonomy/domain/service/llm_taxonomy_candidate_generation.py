import json
import os

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import timezone

from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import ModelName, OpenAIGptConfig
from taxonomy.domain.repository.llm_taxonomy_candidate import (
    LLMTaxonomyCandidateRepository,
)
from taxonomy.models import LLMTaxonomyCandidate
from taxonomy.models import LLMTaxonomyCandidateGenerationJob


class LLMTaxonomyCandidateGenerationError(Exception):
    """
    LLM分類候補生成でユーザーに表示する例外です。
    """


class LLMTaxonomyCandidateGenerationService:
    """
    LLMで分類候補を生成し、レビュー待ち候補として保存するServiceです。
    """

    MODEL_NAME = ModelName.GPT_5_MINI
    MAX_TOKENS = 1600
    PROMPT_VERSION = "taxonomy-candidate-generation-v1"
    TARGET_PROMPT_VERSION = "taxonomy-candidate-targets-v1"

    REQUIRED_FIELDS = [
        "kingdom_name",
        "phylum_name",
        "classification_name",
        "family_name",
        "genus_name",
        "species_name",
        "breed_name",
    ]
    FIELD_LIMITS = {
        field.name: field.max_length
        for field in LLMTaxonomyCandidate._meta.fields
        if getattr(field, "max_length", None)
    }

    @classmethod
    def generate_and_save(cls) -> list[LLMTaxonomyCandidate]:
        """
        LLMで1本の属階層に属する複数の種候補を生成し、レビュー待ちとして保存します。
        """
        target_names = cls._generate_target_names()
        candidates = []
        for target_name in target_names:
            candidate_data_list = cls._generate_candidate_detail(target_name)
            candidates.extend(
                LLMTaxonomyCandidateRepository.create_pending_bulk(candidate_data_list)
            )
        return candidates

    @classmethod
    def start_job(cls, user) -> LLMTaxonomyCandidateGenerationJob:
        """
        画面からポーリング実行するための生成ジョブを作成します。
        """
        return LLMTaxonomyCandidateRepository.create_generation_job(user)

    @classmethod
    def process_next_job_step(
        cls,
        job: LLMTaxonomyCandidateGenerationJob,
    ) -> LLMTaxonomyCandidateGenerationJob:
        """
        生成ジョブを1ステップだけ進め、進捗表示用の状態を保存します。
        """
        if job.status in [
            LLMTaxonomyCandidateGenerationJob.JobStatus.COMPLETED,
            LLMTaxonomyCandidateGenerationJob.JobStatus.FAILED,
        ]:
            return job

        if job.status == LLMTaxonomyCandidateGenerationJob.JobStatus.PENDING:
            return cls._prepare_job_targets(job)

        return cls._generate_next_job_candidate(job)

    @classmethod
    def _prepare_job_targets(
        cls,
        job: LLMTaxonomyCandidateGenerationJob,
    ) -> LLMTaxonomyCandidateGenerationJob:
        job.started_at = timezone.now()
        job.current_step = "生成対象リスト作成"
        job.status = LLMTaxonomyCandidateGenerationJob.JobStatus.RUNNING
        try:
            target_names = cls._generate_target_names()
        except LLMTaxonomyCandidateGenerationError as error:
            job.status = LLMTaxonomyCandidateGenerationJob.JobStatus.FAILED
            job.error_message = str(error)
            job.finished_at = timezone.now()
            LLMTaxonomyCandidateRepository.update_generation_job(
                job,
                [
                    "status",
                    "current_step",
                    "error_message",
                    "started_at",
                    "finished_at",
                ],
            )
            return job

        job.target_names = target_names
        job.total_count = len(target_names)
        job.current_target = target_names[0] if target_names else ""
        if not target_names:
            job.status = LLMTaxonomyCandidateGenerationJob.JobStatus.FAILED
            job.error_message = "生成対象リストが空でした。もう一度生成してください。"
            job.finished_at = timezone.now()
        LLMTaxonomyCandidateRepository.update_generation_job(
            job,
            [
                "status",
                "current_step",
                "target_names",
                "total_count",
                "current_target",
                "error_message",
                "started_at",
                "finished_at",
            ],
        )
        return job

    @classmethod
    def _generate_next_job_candidate(
        cls,
        job: LLMTaxonomyCandidateGenerationJob,
    ) -> LLMTaxonomyCandidateGenerationJob:
        if job.processed_count >= job.total_count:
            job.status = LLMTaxonomyCandidateGenerationJob.JobStatus.COMPLETED
            job.current_step = "完了"
            job.current_target = ""
            job.finished_at = timezone.now()
            LLMTaxonomyCandidateRepository.update_generation_job(
                job,
                ["status", "current_step", "current_target", "finished_at"],
            )
            return job

        target_name = job.target_names[job.processed_count]
        job.current_step = "候補詳細生成"
        job.current_target = target_name
        try:
            candidate_data_list = cls._generate_candidate_detail(target_name)
            candidates = LLMTaxonomyCandidateRepository.create_pending_bulk(
                candidate_data_list
            )
        except LLMTaxonomyCandidateGenerationError as error:
            failures = list(job.failures)
            failures.append({"target": target_name, "message": str(error)})
            job.failures = failures
            job.failed_count = len(failures)
        else:
            candidate_ids = list(job.candidate_ids)
            candidate_ids.extend(candidate.pk for candidate in candidates)
            job.candidate_ids = candidate_ids
            job.success_count += len(candidates)

        job.processed_count += 1
        if job.processed_count >= job.total_count:
            job.status = LLMTaxonomyCandidateGenerationJob.JobStatus.COMPLETED
            job.current_step = "完了"
            job.current_target = ""
            job.finished_at = timezone.now()
        elif job.processed_count < len(job.target_names):
            job.current_target = job.target_names[job.processed_count]

        LLMTaxonomyCandidateRepository.update_generation_job(
            job,
            [
                "status",
                "current_step",
                "current_target",
                "candidate_ids",
                "failures",
                "processed_count",
                "success_count",
                "failed_count",
                "finished_at",
            ],
        )
        return job

    @classmethod
    def _generate_target_names(cls) -> list[str]:
        service = cls._completion_service()
        result = service.retrieve_answer(
            [
                Message(role=RoleType.SYSTEM, content=cls._target_system_prompt()),
                Message(role=RoleType.USER, content=cls._target_user_prompt()),
            ],
            max_messages=2,
        )
        return cls._clean_target_names(result.answer)

    @classmethod
    def _generate_candidate_detail(cls, target_name: str) -> list[dict]:
        service = cls._completion_service()
        result = service.retrieve_answer(
            [
                Message(role=RoleType.SYSTEM, content=cls._system_prompt()),
                Message(
                    role=RoleType.USER, content=cls._detail_user_prompt(target_name)
                ),
            ],
            max_messages=2,
        )
        return cls._clean_candidate_data_list(result.answer)

    @classmethod
    def _completion_service(cls) -> LlmCompletionService:
        api_key = os.getenv("OPENAI_API_KEY") or ""
        if not api_key:
            raise LLMTaxonomyCandidateGenerationError(
                "OPENAI_API_KEY が未設定のため、LLM生成を実行できません。"
            )
        return LlmCompletionService(
            OpenAIGptConfig(
                api_key=api_key,
                model=cls.MODEL_NAME,
                max_tokens=cls.MAX_TOKENS,
            )
        )

    @staticmethod
    def _target_system_prompt() -> str:
        return (
            "あなたは生物分類学データを整理する専門家です。"
            "回答はJSON配列だけにしてください。"
            "配列には今回詳細生成する正式な種名または一般的な和名だけを入れてください。"
            "亜種、品種、系統、地域個体群は候補にしないでください。"
        )

    @classmethod
    def _target_user_prompt(cls) -> str:
        existing_lines = LLMTaxonomyCandidateRepository.existing_hierarchy_lines()
        existing_hierarchy = "\n".join(f"- {line}" for line in existing_lines)
        if not existing_hierarchy:
            existing_hierarchy = "- 既存の分類階層はまだありません。"
        return (
            "Taxonomy アプリへ追加レビューする種候補名だけを3〜6件生成してください。\n"
            "既存階層にあるノードはできるだけ再利用し、まだ薄い枝または未登録の枝から選んでください。\n"
            "1回のジョブでは同じ属に属する種候補だけを返してください。\n"
            "JSON配列の各要素は文字列にしてください。\n"
            "既存の種までの分類階層:\n"
            f"{existing_hierarchy}"
        )

    @classmethod
    def _detail_user_prompt(cls, target_name: str) -> str:
        return (
            f"{target_name} について、Taxonomy アプリへ追加レビューする分類候補を1件だけ生成してください。\n"
            "rootである界から始め、門、綱、科、属、種までの分類階層を埋めてください。\n"
            "species_name と breed_name には同じ値を入れてください。\n"
            "出典で確認できる正式な種名または一般的な和名だけを返してください。\n"
            "JSON配列の要素数は1件にしてください。\n"
            f"JSON配列の各要素のキーは {cls._field_list()} だけにしてください。\n"
            "source_name と source_url は確認元として人間が開ける値を可能な限り入れてください。\n"
            "外部taxonomy IDは確信できる場合だけ入れ、不明なら空文字にしてください。\n"
            "人間が確認すべき注意点は llm_note に短く書いてください。"
        )

    @staticmethod
    def _field_list() -> str:
        fields = [
            "kingdom_name",
            "kingdom_name_en",
            "phylum_name",
            "phylum_name_en",
            "classification_name",
            "classification_name_en",
            "family_name",
            "family_name_en",
            "genus_name",
            "genus_name_en",
            "species_name",
            "species_name_en",
            "breed_name",
            "breed_name_kana",
            "source_name",
            "source_url",
            "external_taxon_id",
            "llm_note",
        ]
        return ", ".join(fields)

    @classmethod
    def _system_prompt(cls) -> str:
        return (
            "あなたは生物分類学データを整理する専門家です。"
            "回答はJSON配列だけにしてください。"
            "1回の回答では、界から属までの分類階層パスを1本だけ扱ってください。"
            "その同じ属に属する種候補を複数件返してください。"
            "亜種、品種、系統、地域個体群は候補にしないでください。"
            "species_nameとbreed_nameには同じ種名を入れてください。"
            "地域名や国名からラテン名風の亜種・系統名を作らないでください。"
            "正式な出典で確認できない候補は返さず、件数が少なくなっても構いません。"
            "分類階層、出典名、出典URLは可能な限り埋めてください。"
            "GBIF、Catalogue of Life、iNaturalist、Wikipediaなど公開情報で確認しやすい出典を優先してください。"
            "外部taxonomy IDは確信できる場合だけ入れ、不明なら空文字にしてください。"
            "推定を含む場合は llm_note に明記してください。"
        )

    @classmethod
    def _user_prompt(cls) -> str:
        existing_lines = LLMTaxonomyCandidateRepository.existing_hierarchy_lines()
        existing_hierarchy = "\n".join(f"- {line}" for line in existing_lines)
        if not existing_hierarchy:
            existing_hierarchy = "- 既存の分類階層はまだありません。"
        field_list = cls._field_list()
        return (
            "Taxonomy アプリへ追加レビューする分類候補を生成してください。\n"
            "rootである界から始め、門、綱、科、属へと1本の分類階層だけをたどってください。\n"
            "既存階層にあるノードはできるだけ再利用し、まだ薄い枝または未登録の枝を1本だけ伸ばしてください。\n"
            "たとえば動物界はあるが節足動物門が薄い、または未登録なら、節足動物門から属まで1本を提案してください。\n"
            "界、門、綱、科、属はJSON配列内の全要素で同じ値にし、その属に属する種だけを3〜6件生成してください。\n"
            "species_nameは候補ごとに分類学上正しい種名にしてください。たとえばアジアミツバチならspecies_nameはアジアミツバチまたはApis ceranaにし、ニホンミツバチにしないでください。\n"
            "species_nameはJSON配列内で全件異なる値にしてください。\n"
            "breed_nameは画面に出すキャプションです。breed_nameにはspecies_nameと同じ値を入れてください。\n"
            "species_nameやbreed_nameがBetta splendensのような学名で、species_name_enがSiamese fighting fishのような別表記の英名・通称になる場合は、llm_noteに両者が同じ種を指す根拠と確認元を短く書いてください。\n"
            "同じ種の根拠を書けない場合は、species_name_enを空にするか、その候補を返さないでください。\n"
            "ニホンミツバチのような亜種、地域個体群、飼育系統は候補にしないでください。\n"
            "コリアナ系統 (Apis cerana koreana) のような、地域名から作った未確認の亜種名・系統名は返さないでください。\n"
            "出典で確認できる正式な種名または一般的な和名だけを返してください。\n"
            "こうすると承認が進むほど既存ノードを再利用でき、次回以降の生成とレビューが短くなります。\n"
            "既存のニワトリ分類だけに偏らず、養蜂、観賞魚、研究生物、養蚕、飼育昆虫、家畜などから1本を選んでください。\n"
            "既存の種までの分類階層:\n"
            f"{existing_hierarchy}\n"
            f"JSON配列の各要素のキーは {field_list} だけにしてください。\n"
            "breed_name は species_name と同じ値にしてください。\n"
            "学名を併記したい場合でも、species_name と breed_name の表記は必ず一致させてください。\n"
            "breed_name_kana は日本語よみがなにしてください。\n"
            "source_name と source_url は確認元として人間が開ける値を可能な限り入れてください。\n"
            "人間が確認すべき注意点は llm_note に短く書いてください。"
        )

    @classmethod
    def _clean_candidate_data_list(cls, answer: str) -> list[dict]:
        raw_items = cls._load_json_array(answer)
        cleaned_items = []
        seen_names = set()
        seen_species_names = set()
        hierarchy_key = None
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            cleaned = cls._clean_candidate_data(item)
            item_hierarchy_key = cls._hierarchy_key(cleaned)
            if hierarchy_key is None:
                hierarchy_key = item_hierarchy_key
            if item_hierarchy_key != hierarchy_key:
                continue
            cls._validate_species_caption(cleaned)
            species_name = cleaned["species_name"]
            if species_name in seen_species_names:
                raise LLMTaxonomyCandidateGenerationError(
                    "LLM生成結果の種名が重複しています。もう一度生成してください。"
                )
            breed_name = cleaned["breed_name"]
            if breed_name in seen_names:
                continue
            if LLMTaxonomyCandidateRepository.breed_exists(breed_name):
                continue
            seen_species_names.add(species_name)
            seen_names.add(breed_name)
            cleaned_items.append(cleaned)

        if not cleaned_items:
            raise LLMTaxonomyCandidateGenerationError(
                "保存できるLLM生成候補がありませんでした。もう一度生成してください。"
            )
        return cleaned_items

    @staticmethod
    def _hierarchy_key(candidate_data: dict) -> tuple[str, str, str, str, str]:
        return (
            candidate_data["kingdom_name"],
            candidate_data["phylum_name"],
            candidate_data["classification_name"],
            candidate_data["family_name"],
            candidate_data["genus_name"],
        )

    @classmethod
    def _clean_candidate_data(
        cls,
        raw_data: dict,
    ) -> dict:
        cleaned = {}
        for field_name in LLMTaxonomyCandidateSaveFields.names():
            value = raw_data.get(field_name, "")
            if value is None:
                value = ""
            value = str(value).strip()
            max_length = cls.FIELD_LIMITS.get(field_name)
            if max_length:
                value = value[:max_length]
            cleaned[field_name] = value

        cleaned["source_url"] = cls._clean_source_url(cleaned["source_url"])
        cleaned["llm_note"] = cls._build_llm_note(cleaned.get("llm_note", ""))

        missing = [field for field in cls.REQUIRED_FIELDS if not cleaned.get(field)]
        if missing:
            labels = "、".join(missing)
            raise LLMTaxonomyCandidateGenerationError(
                f"LLM生成結果に必須項目が不足しています: {labels}"
            )

        candidate = LLMTaxonomyCandidate(**cleaned)
        try:
            candidate.full_clean()
        except ValidationError as error:
            raise LLMTaxonomyCandidateGenerationError(
                "LLM生成結果を候補として保存できません。入力内容を見直してください。"
            ) from error

        return cleaned

    @staticmethod
    def _validate_species_caption(candidate_data: dict) -> None:
        species_name = candidate_data["species_name"].strip()
        breed_name = candidate_data["breed_name"].strip()
        if species_name == breed_name:
            return
        raise LLMTaxonomyCandidateGenerationError(
            "LLM生成結果の種名とキャプションが一致していません。もう一度生成してください。"
        )

    @staticmethod
    def _clean_source_url(source_url: str) -> str:
        if not source_url:
            return ""

        normalized_url = source_url
        if normalized_url.startswith("www."):
            normalized_url = f"https://{normalized_url}"

        try:
            URLValidator()(normalized_url)
        except ValidationError:
            return ""
        return normalized_url

    @staticmethod
    def _load_json_array(answer: str) -> list:
        text = answer.strip()
        if "```" in text:
            lines = [line.strip() for line in text.splitlines()]
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and start < end:
            text = text[start : end + 1]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise LLMTaxonomyCandidateGenerationError(
                "LLM生成結果をJSONとして読み取れませんでした。もう一度生成してください。"
            ) from error
        if not isinstance(data, list):
            raise LLMTaxonomyCandidateGenerationError(
                "LLM生成結果が候補配列ではありません。もう一度生成してください。"
            )
        return data

    @classmethod
    def _clean_target_names(cls, answer: str) -> list[str]:
        raw_items = cls._load_json_array(answer)
        target_names = []
        seen_names = set()
        for item in raw_items:
            if not isinstance(item, str):
                continue
            target_name = item.strip()
            if not target_name or target_name in seen_names:
                continue
            target_names.append(target_name[:255])
            seen_names.add(target_name)
            if len(target_names) >= 6:
                break

        if not target_names:
            raise LLMTaxonomyCandidateGenerationError(
                "LLM生成対象リストを読み取れませんでした。もう一度生成してください。"
            )
        return target_names

    @classmethod
    def _build_llm_note(cls, note: str) -> str:
        metadata = f"model={cls.MODEL_NAME}; prompt={cls.PROMPT_VERSION}"
        if not note:
            return metadata
        return f"{note}\n{metadata}"


class LLMTaxonomyCandidateSaveFields:
    """
    LLM候補として保存する入力フィールド名を返します。
    """

    @staticmethod
    def names() -> list[str]:
        return [
            "kingdom_name",
            "kingdom_name_en",
            "phylum_name",
            "phylum_name_en",
            "classification_name",
            "classification_name_en",
            "family_name",
            "family_name_en",
            "genus_name",
            "genus_name_en",
            "species_name",
            "species_name_en",
            "breed_name",
            "breed_name_kana",
            "source_name",
            "source_url",
            "external_taxon_id",
            "llm_note",
        ]
