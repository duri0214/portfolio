# （途中）AI Agent を試作する

## はじめに

これは会話型のマルチエージェントシステムです。各エージェント（エンティティ）が専門領域を持ち、RAGやモデレーション（ガードレール）を使いながら応答を作ります。現状は、ターン制で順にエージェントを動かすターン式AIチャットとして実装しています。

![AI Agentの会話フロー](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/94562/f44613c5-c35e-421e-b1cd-f302baacc91a.png)

## Source

https://github.com/duri0214/portfolio/tree/master/ai_agent

## TODO

- [ガードレールの「信号機」](https://github.com/duri0214/portfolio/issues/310)
- [ContextAnalyzerServiceにベクトル検索ベースのRAG実装を追加](https://github.com/duri0214/portfolio/issues/324)

## アーキテクチャ概要

- コア概念: 複数エージェント（Entity）が行動順序（Turn）に従って会話を生成する。
- 検索・知識基盤: `fixtures/rag_material.json` などのRAG材料を利用する。
- 安全性: 静的ガードレール（禁止ワードなど）と動的ガードレール（OpenAI Moderation API想定）を組み合わせる。
- 永続化: `ActionHistory` や `Message` などのモデルで会話履歴を管理する。

## 典型的な処理フロー（1ターンのライフサイクル）

1. ユーザーがテキストを送信し、`IndexView` がリクエストを受ける。
2. `InputProcessor` がガードレールチェックを実施する。
   - ユーザー入力の安全性を審査する。
   - 問題がなければ加工済みメッセージを返し、危険な入力ならエラー応答にする。
3. `TurnManagement` が現在のターンのエンティティを取得する。
   - ユーザーに発言権がない場合はエラー応答にする。
4. `ContextAnalyzer` が文脈を整形し、RAGを参照してLLM応答を生成する。
   - 必要に応じて外部情報や素材もRAG処理経由で参照する。
5. `TurnManagementRepository` を通じて `Message` を保存し、`ActionHistory` を `done=True` に更新する。
6. 次の未処理 `ActionHistory` を取得し、ユーザーに次のエンティティ情報を返す。

## 主要コンポーネント

### 1. Factory層（ファクトリー層）

Factory層は、入力された情報やタイプに応じて、値オブジェクトやドメインオブジェクトを組み立てて返す層です。呼び出し元は、どの型を生成するかをFactoryの外で意識せずに済みます。

この構造により、次のことができます。

- 種類に応じた生成ロジックをFactory内部に集約できる。
- 新しい型や生成ロジックを追加しても、利用側の変更を小さくできる。
- 同じインターフェースで複数のValue ObjectやEntityを生成できる。

RAG素材のように、外部ソースごとにメタデータ形式が異なる場合は、`material_type` をキーにして該当するクラスを生成します。具体的な実装例として `RagMetadataFactory` があり、`create(material_type, metadata_dict)` のようなインターフェースで利用します。

#### Factory層の利用例

- Slack、Gmail、マニュアル、PDF、Google Mapなど、素材タイプごとのメタデータを統一的に扱う。
- Value Objectが増えても、呼び出し元が具体クラスを直接判定しない。
- Factoryの実装を差し替えて、扱う素材や型を拡張する。

### 2. Repository層（リポジトリ層）

Repository層は、ドメインオブジェクトやValue Objectをデータストアから取得・保存する処理を集約する層です。DBや外部APIなどの物理的なデータソースへのアクセスを、ドメインロジックやService層から隠蔽します。

この構造により、次のことができます。

- 取得条件や保存処理を共通化できる。
- DB、外部サービス、検索エンジンなどの変更時に、実装の差し替え範囲を限定できる。
- 上位層が「どこに保存するか」ではなく「何を取得・保存するか」に集中できる。

具体的な実装例として `ContextAnalyzerRepository` と `TurnManagementRepository` があります。前者は `get_rag_source_merged(material_type)`、後者は `find_next_turn_entity()` のように、意図が分かるインターフェースを持ちます。

#### Repository層の利用例

- `material_type` を指定して、RAG素材をまとめて取得する。
- 会話のターンや `ActionHistory` を条件付きで取得・追加・更新する。
- 将来的に全文検索、ベクトル検索API、NoSQL、キャッシュへ変更する場合も、Service層への影響を抑える。

### 3. Service層（サービス層）

Service層は、複数のRepositoryやドメインオブジェクトを組み合わせ、業務シナリオ単位の処理をまとめる層です。ViewやControllerからは、個別のDB操作ではなく、業務目的に対応するServiceを呼び出します。

具体的には、次のような処理をService層に集約します。

- `InputProcessor`: 入力テキストのサニタイズ、ガードレール判定、LLMや外部サービスとの連携。
- `TurnManagementService`: ターン数の更新、シミュレーション、リセット、進行状況の記録。
- `ContextAnalyzerService`: 文脈や思考タイプの分類、キーワード抽出、関連エンティティの再構成。

Service層が処理の順序や組み合わせを担うことで、Viewは「何をしたいか」をServiceに伝える役割に集中できます。

### 4. Value Object層（値オブジェクト層）

Value Object層は、業務上の意味や制約を持つ値を、不変なデータ構造として表現する層です。単なる辞書やプリミティブ型ではなく、値のまとまりと正しさを1つのオブジェクトで扱います。

Value Objectには、次のような責務を持たせます。

- 複数の値を業務上意味のある単位にまとめる。
- 必須項目、範囲、形式などの制約を生成時に検証する。
- `from_dict()` や `to_dict()` でAPI・永続化層との変換を一元化する。
- 日付のISO形式変換など、値に固有の変換処理を閉じ込める。

#### Value Objectの利用例

- Google Mapsレビューの評価、緯度経度、著者名、レビュー日時、場所を `GoogleMapsMetadata` で扱う。
- PDFやRAG素材のファイルパスなど、必須情報を `PdfSourceMetadata` で扱う。
- 禁止ワードや違反カテゴリなどの入力検査結果を `GuardrailResult` で扱う。
- エンティティやターンの状態を、その時点のスナップショットとして扱う。
- `EntityVO`、`InputProcessorConfig` など、ドメイン上の意味を持つ値を型として流通させる。

検証済みのValue ObjectをService層へ渡すことで、不正なデータを早期に拒否し、呼び出し側の分岐を減らせます。

## 実装との対応

現時点の主な実装は次のとおりです。

- `ai_agent/domain/factory/rag_metadata_factory.py`
- `ai_agent/domain/repository/context_analyzer.py`
- `ai_agent/domain/repository/turn_management.py`
- `ai_agent/domain/service/input_processor.py`
- `ai_agent/domain/service/context_analyzer.py`
- `ai_agent/domain/service/turn_management.py`
- `ai_agent/domain/valueobject/input_processor.py`
- `ai_agent/domain/valueobject/context_analyzer.py`
- `ai_agent/domain/valueobject/turn_management.py`

このページは現時点の設計と実装を整理するためのものです。ベクトル検索の本格導入やガードレールの状態表示など、未実装または改善途中の内容は、関連IssueとPhase 2で扱います。

## 参考

- [AI AgentのREADME](https://github.com/duri0214/portfolio/blob/master/ai_agent/README.md)
- [Phase 1: Qiita記事をGitHub化](https://github.com/duri0214/portfolio/issues/903)
- [親チケット: Qiita記事のGitHub化と大改修](https://github.com/duri0214/portfolio/issues/902)
- [Phase 2: AI Agentの大改修](https://github.com/duri0214/portfolio/issues/904)
