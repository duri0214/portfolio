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
    国会議事録を「思考のためのデータ変換装置」へと昇華させるナレッジ工場のパイプライン。

    [設計思想: ドメイン粒度で並べたバッチの連なり]
    このパイプラインは、単なる技術的な処理の羅列ではなく、国会の制度や議論の構造（ドメイン）に
    即した抽象度で設計された、一連のバッチ処理の連なりです。

    同じドメイン抽象度の処理をバッチ単位で直列に接続することで、
    巨大なJSONデータを、政治を観測し思考するための「知識構造」へと変換します。

    工程バッチフロー:
    [開催日バッチ] ─▶ [会議バッチ] ─▶ [議題バッチ] ─▶ [発言バッチ] ─▶ [話題バッチ:RAG]

    各工程は「国会の議論構造」を復元しながら価値を付与し、
    最終的に市民が政治を多角的に理解できる知識インフラへと昇華させます。
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
        [工程1: 開催日バッチ ─▶ 会議バッチ]
        指定された日付範囲（開催日粒度）を巡回し、各開催日に含まれる会議（会議粒度）を抽出する。
        大量の会議録をAPIから取得し、1件ずつのドメインオブジェクトとして後続の工程に投入する。
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

            for a_meeting in result.meeting_records:
                print(
                    f"  Processing: {a_meeting.date} {a_meeting.name_of_meeting} {a_meeting.issue}"
                )
                try:
                    self._process_meeting_record(a_meeting)
                except Exception as e:
                    print(f"    Error processing a_meeting {a_meeting.issue_id}: {e}")
                    # 1つの会議の失敗が、期間全体のバッチ処理を止めないように制御する。
                    # エラーが発生した会議のDB/RAG変更は _process_meeting_record 内でロールバックされるが、
                    # それ以前に完了した会議のデータは保持される。
                    continue

            if (
                not result.next_record_position
                or result.next_record_position > result.number_of_records
            ):
                break
            current_start = result.next_record_position
        print("Pipeline execution completed.")

    def _process_meeting_record(self, a_meeting: MeetingRecord):
        """
        [工程2-5: 会議 ─▶ 議題 ─▶ 発言 ─▶ 話題バッチ]
        1つの会議（会議粒度）を、議題・発言・話題（論点）というドメイン粒度に沿って分解・変換する。

        このメソッドは、1つの会議録をドメインの抽象度を下げながら価値を高めるプロセスを担います：

        - 工程2: 会議バッチ (DB保存): 会議の基本情報を永続化する。
          ※ Meeting テーブルは「1会議（セッション）につき 1レコード」として保持されます。
        - 工程3: 議題バッチ (文脈化): 会議内を意味のある議題・論点セクションに分割する。
          ※ 議題名は RAG のメタデータとしてのみ活用され、DBのレコード分割には影響しません。
        - 工程4: 発言バッチ: 各発言を Speech レコードとして保存し、ベクトル化（Embedding）を行う。
        - 工程5: 話題バッチ (RAG登録): ベクトルデータを知識ベースに格納し、検索可能にする。

        [エラーハンドリングと整合性]
        transaction.atomic() により、このメソッド内（1つの会議単位）の処理はアトミックに保証されます。
        途中でエラーが発生した場合は、その会議に関するDBおよびベクトルDBへの変更のみがロールバックされます。
        呼び出し元のループ全体がロールバックされることはありません。
        """
        with transaction.atomic():
            meeting_obj, created = Meeting.objects.update_or_create(
                min_id=a_meeting.issue_id,
                defaults={
                    "meeting_date": a_meeting.date_obj,
                    "session_number": a_meeting.session,
                    "house": a_meeting.name_of_house,
                    "committee": a_meeting.name_of_meeting,
                    "meeting_number": a_meeting.issue,
                    "url": a_meeting.meeting_url,
                },
            )
            if not created:
                meeting_obj.speeches.all().delete()
            agendas = self._split_by_agenda(a_meeting)
            total_speech_order = 0
            rag_docs = []
            for agenda_title, speeches in agendas:
                for s in speeches:
                    total_speech_order += 1
                    role = s.speaker_role
                    Speech.objects.create(
                        meeting=meeting_obj,
                        speaker_name=s.speaker,
                        speaker_role=role,
                        speaker_affiliation=s.speaker_group,
                        speech_text=s.speech or "",
                        speech_order=total_speech_order,
                    )
                    if self.rag_service and s.speech:
                        stable_id_prefix = f"{a_meeting.issue_id}_{total_speech_order}"
                        doc = RagDocument(
                            page_content=s.speech,
                            metadata={
                                "meeting_date": a_meeting.date,
                                "session_number": a_meeting.session,
                                "house": a_meeting.name_of_house,
                                "committee": a_meeting.name_of_meeting,
                                "meeting_number": a_meeting.issue,
                                "agenda_title": agenda_title,
                                "speaker_name": s.speaker,
                                "speaker_role": role or "",
                                "url": a_meeting.meeting_url,
                                "id": stable_id_prefix,
                            },
                        )
                        rag_docs.append(doc)
            if self.rag_service and rag_docs:
                self.rag_service.upsert_documents(rag_docs)

    @staticmethod
    def _split_by_agenda(
        a_meeting: MeetingRecord,
    ) -> list[tuple[str, list[SpeechRecord]]]:
        """
        [工程3: 議題バッチ]
        会議録という巨大なテキストバッチを、議論の主題（ドメイン境界）に基づいて、
        より小さな「議題・論点バッチ」へと再構成する。

        [なぜ upsert_documents の自動分割があるのに、このメソッドが必要なのか]
        lib/llm/service/completion.py の upsert_documents で行われる分割は、
        あくまで「APIの制限を回避するための技術的な固定長分割」です。
        一方、この _split_by_agenda は「国会の議論構造に基づいた意味的な分割」を行います。

        これは、LangChain等で長大なPDFを処理する際に、各チャンクに「ページ番号」や
        「章タイトル」をメタデータとして付与し、分割後も元の文脈を辿れるようにする手法と同じ設計思想です。

        [話の流れの整合性について]
        このメソッドによる「砕き」は、発言の時系列順序を一切崩しません。
        単に発言の連なりの上に「ここからこの話題」というインデックス（しおり／ブックマーク）を置くだけの処理です。
        そのため、話の流れがガチャガチャになることはなく、文脈を維持したまま構造化が可能です。

        [人間境界とAI境界の両立]
        この設計により、以下の2つの境界を両立させています：
        1. MySQL（人間境界）: ユーザーが閲覧する単位（1会議1レコード）。
        2. Chroma DB（AI境界）: 検索に最適化された単位（議題メタデータ付きの細かいチャンク）。

        このメソッドを維持することで以下の価値が生まれます：
        1. 意味的なメタデータの付与:
           各発言に「どの議題の下で行われたか」という agenda_title メタデータを付与できます。
           技術的に「バナナが腐る」がちぎれたとしても、「腐敗のメカニズムに関する議題」という
           強力な文脈を保持したまま検索・回答生成が可能になります。
        2. RAG精度の向上:
           検索時に「議題名」が補助情報として機能し、生成時にはLLMが「この発言はどのトピックの審議中か」
           を正しく理解できるようになります。
        3. 制度への適合:
           国会というドメインの性質（議題単位の進行）をデータ構造に反映できます。

        この工程は、単なるテキスト分割ではなく、国会の議論構造をデータ上に復元する「意味的再構成」であり、
        技術的な制約回避とは独立した、ナレッジの価値を高めるための必須工程です。
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

        for s in a_meeting.speech_records:
            if not s.speech:
                current_speeches.append(s)
                continue

            agenda_match = agenda_pattern.match(s.speech.strip())
            if agenda_match:
                # 新しい議題の開始
                if current_speeches:
                    agendas.append((current_agenda_title, current_speeches))
                current_agenda_title = agenda_match.group(1)
                current_speeches = [s]
            else:
                current_speeches.append(s)

        if current_speeches:
            agendas.append((current_agenda_title, current_speeches))

        return agendas
