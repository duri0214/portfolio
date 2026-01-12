import re
from datetime import date

from django.db import transaction
from ...models import Meeting, Speech
from .kokkai_api import KokkaiAPIClient
from ..valueobject.meeting import MeetingRecord, SpeechRecord

from lib.llm.service.completion import OpenAILlmRagService
from lib.llm.valueobject.completion import RagDocument
import os


class KokkaiPipeline:
    """
    国会議事録を「検索可能な知識」へと変換するナレッジ工場のパイプライン。

    [思想: 知識のバリューチェーン]
    原材料（国会議事録HTML）から最終製品（政治的ナレッジ/RAG基盤）を生成する、
    横並びの製造ライン（パイプライン）として設計されています。

    工程フロー:
    [取得:API] ─▶ [正規化] ─▶ [会議抽出] ─▶ [議題分割] ─▶ [発言分割] ─▶ [意味理解:Embedding] ─▶ [登録:Chroma]

    各工程は独立しており、原材料に構造と意味という「価値」を付与しながら、
    最終的に市民がAIを通じて質問できる知識インフラへと昇華させます。
    """

    def __init__(self, api_key: str | None = None):
        self.client = KokkaiAPIClient()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if self.api_key:
            self.rag_service = OpenAILlmRagService(
                model="gpt-4o",  # 適宜調整
                api_key=self.api_key,
                collection_name="kokkai_speeches",
            )
        else:
            self.rag_service = None

    def process_and_save_meetings(self, start_date: date, end_date: date):
        """
        [工程1: 取得・巡回]
        指定期間の会議をAPIから取得し、製造ラインに投入する。
        大量のデータをバッチ単位で取得し、1件ずつの会議レコードへと正規化する。
        """
        print(f"Starting pipeline for period: {start_date} to {end_date}")
        current_start = 1
        while True:
            result = self.client.search_meetings(
                start_date, end_date, start_record=current_start
            )
            if not result.meeting_records:
                print("No more meeting records found.")
                break

            total = result.number_of_records
            print(f"Processing batch starting at {current_start} / {total}")

            for record in result.meeting_records:
                print(
                    f"  Processing: {record.date} {record.name_of_meeting} {record.issue}"
                )
                try:
                    self._process_meeting_record(record)
                except Exception as e:
                    print(f"    Error processing record {record.issue_id}: {e}")
                    # 個別の失敗で全体を止めないようにするか検討の余地ありだが、
                    # 現状はデバッグしやすくするために継続
                    continue

            if (
                not result.next_record_position
                or result.next_record_position > result.number_of_records
            ):
                break
            current_start = result.next_record_position
        print("Pipeline execution completed.")

    def _process_meeting_record(self, record: MeetingRecord):
        """
        [工程2-5: 構造化・分解・Embedding・登録]
        1つの会議録（1日・1委員会単位）を処理する中核工程。

        1. 議題単位に分割（構造化）
        2. DBへの保存（永続化）
        3. 発言単位への細分化（分解）
        4. ベクトル化（意味理解）
        5. Chroma DBへの登録（検索可能化）

        この工程により、単なるテキストが「検索可能な構造データ」へと価値を変える。
        """
        # 国会議事録のspeechRecordの中で、議題は通常 "○" で始まる。
        # 例: "○議題１に関する件"

        agendas = self._split_by_agenda(record)

        for agenda_order, (agenda_title, speeches) in enumerate(agendas, 1):
            with transaction.atomic():
                # Meetingレコード作成 (既存があれば更新)
                meeting_obj, created = Meeting.objects.update_or_create(
                    min_id=record.issue_id,
                    agenda_order=agenda_order,
                    defaults={
                        "meeting_date": record.date_obj,
                        "session_number": record.session,
                        "house": record.name_of_house,
                        "committee": record.name_of_meeting,
                        "meeting_number": record.issue,
                        "agenda_title": agenda_title,
                        "url": record.meeting_url,
                    },
                )

                if not created:
                    # 既存のSpeechレコードを削除（再投入するため）
                    # 関連するChromaドキュメントも上書きされるので、DB側は一旦クリアするのが安全
                    meeting_obj.speeches.all().delete()

                # Speechレコード作成
                speech_objs = []
                rag_docs = []
                for order, s in enumerate(speeches, 1):
                    # speaker_role, speaker_affiliation の抽出（簡易的）
                    # 本来は正規表現などで詳細に分けるべきだが、まずはシンプルに
                    role = s.speaker_role

                    speech_obj = Speech.objects.create(
                        meeting=meeting_obj,
                        speaker_name=s.speaker,
                        speaker_role=role,
                        speaker_affiliation=s.speaker_group,
                        speech_text=s.speech or "",
                        speech_order=order,
                    )
                    speech_objs.append(speech_obj)

                    # ベクトル化用ドキュメント
                    if self.rag_service and s.speech:
                        # 安定したIDを生成する (Speech.id は create ごとに変わるため)
                        # min_id + agenda_order + speech_order + chunk_index で一意に特定可能にする
                        stable_id_prefix = f"{record.issue_id}_{agenda_order}_{order}"
                        doc = RagDocument(
                            page_content=s.speech,
                            metadata={
                                "meeting_date": record.date,
                                "session_number": record.session,
                                "house": record.name_of_house,
                                "committee": record.name_of_meeting,
                                "meeting_number": record.issue,
                                "agenda_title": agenda_title,
                                "speaker_name": s.speaker,
                                "speaker_role": role or "",
                                "url": record.meeting_url,
                                "id": stable_id_prefix,
                            },
                        )
                        rag_docs.append(doc)

                # Chroma DBへ登録
                if self.rag_service and rag_docs:
                    self.rag_service.upsert_documents(rag_docs)

    @staticmethod
    def _split_by_agenda(record: MeetingRecord) -> list[tuple[str, list[SpeechRecord]]]:
        """
        [工程2: 議題分割]
        会議録を発言内容に基づいて議題（アジェンダ）や論点ごとに分割する。

        [なぜ分割が必要か: RAGフレンドリな構造化]
        国会議事録は1つの会議が数時間に及び、その中で複数の独立した議題や論点が話し合われます。
        これらを単一のレコードとして扱うのではなく、意味的な境界（議題の切り替わり）で分割することには
        以下の重要なメリットがあります：

        1. 検索精度の向上 (RAG最適化):
           ベクトル検索において、巨大な文書よりも「特定の話題」に絞られた単位のほうが、
           クエリとの意味的な適合度（類似度）を正確に計算できます。
        2. 文脈の維持:
           発言がどの議題（文脈）の中で行われたかをメタデータとして保持することで、
           LLMが回答を生成する際に「何についての議論か」を正しく把握できます。
        3. 閲覧性の改善:
           UI上で長い議事録を論点ごとに構造化して表示できるため、
           ユーザーが目的の議論を素早く見つけられる「思考対象」としてのインターフェースを実現します。

        この工程により、非構造な発言の羅列から、議論の主題という「文脈の境界」を抽出します。
        """
        agendas = []
        # 議題（○...）が検出される前の発言（開会宣言や出席議員の報告など）を
        # 「冒頭」という仮想的な議題タイトルでグループ化する。
        current_agenda_title = "冒頭"
        current_speeches = []

        # 議題の開始を検知するパターン
        # 1. 委員長が「○○に関する件」等を議題とすることを宣言する場合
        # 2. 質疑者が「○○について」と具体的な論点を提示して質疑を始める場合
        # これらを拾うことで、数時間に及ぶ会議を意味のある「セクション」に分割する。
        agenda_pattern = re.compile(
            r"○(?:.+委員長|.+議長|.+君|.+委員)　(.+(?:に関する件|について|の件|法律案（.+）)(?:について調査を進めます|を議題といたします|について質疑を行います|について伺います))"
        )

        for s in record.speech_records:
            if not s.speech:
                current_speeches.append(s)
                continue

            match = agenda_pattern.match(s.speech.strip())
            if match:
                # 新しい議題の開始
                if current_speeches:
                    agendas.append((current_agenda_title, current_speeches))
                current_agenda_title = match.group(1)
                current_speeches = [s]
            else:
                current_speeches.append(s)

        if current_speeches:
            agendas.append((current_agenda_title, current_speeches))

        return agendas
