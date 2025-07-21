# AI Agent プロジェクト

## 概要

このプロジェクトはDjangoフレームワークを使用した会話型AIエージェントシステムです。複数のAIエージェント（エンティティ）による対話型のコミュニケーションを実現し、ユーザー入力の安全性を確保しながら、様々な情報源に基づいた応答生成を行います。

## プロジェクト構造

```
ai_agent/
├── domain/                # ドメイン層（DDD設計）
│   ├── service/           # ビジネスロジックサービス
│   │   ├── conversation.py  # 会話管理サービス
│   │   ├── googlemaps_review.py  # Googleマップレビュー分析
│   │   ├── input_processor.py  # 入力処理・ガードレール
│   │   ├── ng_word.py      # 禁止ワード処理
│   │   └── rag.py          # RAG（検索拡張生成）処理
│   ├── repository/        # データアクセス層
│   │   └── conversation.py  # 会話データリポジトリ
│   └── valueobject/       # 値オブジェクト
│       ├── conversation.py  # 会話関連の値オブジェクト
│       └── input_processor.py  # 入力処理の値オブジェクト
├── tests/                 # テスト
│   ├── test_input_processor.py  # 入力処理テスト
│   ├── test_conversation.py     # 会話管理テスト
│   └── test_next_turn_logic.py  # ターン管理テスト
├── fixtures/              # フィクスチャーデータ
│   └── entity.json        # エンティティデータ
├── migrations/            # DBマイグレーション
└── 各種Djangoファイル
    ├── models.py          # データモデル
    ├── views.py           # ビュー
    ├── urls.py            # URL設定
    ├── forms.py           # フォーム
    └── admin.py           # 管理画面設定
```

## 主要コンポーネント

### 1. 会話管理システム (ConversationService)

`domain/service/conversation.py`にあるConversationServiceは、エージェント間の会話の流れを制御します。

主な機能：

- エンティティのターン管理（速度に基づいた次の発言順序の決定）
- エンティティの思考ロジック（think）による応答可否の判断
- タイムラインの初期化と更新
- 次のアクションのシミュレーション

処理フロー：

1. タイムラインの初期化（initialize_timeline）
2. 入力テキストに対する次のエンティティの決定（get_next_entity）
3. 各エンティティのthinking_typeに基づいた応答可否の判断（think）
4. 次のターンの計算と更新

### 2. 入力処理システム (InputProcessor)

`domain/service/input_processor.py`の入力処理システムは、ユーザー入力の安全性確保と処理を担当します。

主な機能：

- ガードレール機能による入力検証
    - 静的ガードレール（禁止ワード、文字数制限、スパム検出）
    - 動的ガードレール（OpenAI Moderation API）
- セキュリティ対策（XSS対策、入力サニタイゼーション）
- OpenAI Agents SDKを使用した応答生成
- Unicode文字や多言語処理のサポート

特徴：

- エンティティごとにカスタマイズ可能なガードレール設定
- リスクレベルに基づいた処理分岐
- 堅牢なエラーハンドリングとフォールバック処理

### 3. 特殊応答生成サービス

複数の応答生成サービスにより、様々なコンテキストでの対話が可能です：

- **GoogleMapsReviewService** (`domain/service/googlemaps_review.py`)
    - Googleマップのレビューデータに基づいた応答生成
    - `can_respond`メソッドで応答可否を判断

- **RagService** (`domain/service/rag.py`)
    - RAG（検索拡張生成）を用いた高度な応答生成
    - 特定のナレッジベースを活用した情報提供

- **NGWordService** (`domain/service/ng_word.py`)
    - 禁止ワードに基づいた応答制御
    - コンテンツの安全性確保

### 4. データアクセス層

`domain/repository`にあるリポジトリクラスは、データベースとのやり取りを抽象化します：

- **ConversationRepository**
    - エンティティと会話データの取得・更新
    - タイムラインの管理

## 処理の流れ

典型的なチャットのライフサイクル：

1. ユーザーがテキスト入力を送信
2. `InputProcessor`が入力を処理・検証
    - ガードレールによる検証
    - 適切な処理方法の選択
3. `ConversationService.get_next_entity`が次の応答エンティティを決定
4. エンティティの`thinking_type`に基づいて応答可能性を判断
    - GoogleMapsReviewService、RagService、NGWordServiceなどを利用
5. 応答可能な場合、エンティティが応答を生成
6. タイムラインが更新され、次のターンの準備

## モデル

主要なデータモデル：

- **Entity**: AIエージェントエンティティ
    - name, thinking_type, speed等の属性

- **GuardrailConfig**: ガードレール設定
    - 禁止ワード、文字数制限等の安全性設定

- **ActionTimeline**: エンティティの行動タイミング管理
    - next_turn, can_act等の属性

- **ActionHistory**: 過去の行動履歴
    - acted_at_turn, done等の属性

- **Message**: 会話メッセージ

- **GooglemapsReview**: Googleマップのレビューデータ

## 拡張と貢献

このプロジェクトは、新しい応答生成メカニズムやエンティティタイプの追加によって拡張できます：

1. 新しい`thinking_type`を定義
2. 対応するサービスクラスを実装
3. `ConversationService.think`メソッドに新しいタイプの処理を追加

## テスト

本プロジェクトでは以下の主要なテストが実装されています：

### 1. InputProcessorTest (`tests/test_input_processor.py`)

入力処理とガードレール機能のテスト：

- 基本的な入力処理テスト
- 空入力や空白のみの入力処理
- 文字数制限超過テスト
- 静的ガードレール（禁止ワード）テスト
- 動的ガードレール（OpenAI Moderation API）テスト
- APIエラーハンドリングテスト
- 複数ガードレールの同時適用テスト
- リスクレベル分類テスト
- 処理時間測定テスト
- 入力サニタイゼーションテスト
- Unicode文字処理テスト

### 2. ConversationServiceTest (`tests/test_conversation.py`)

会話管理システムのテスト：

- エンティティのターン管理テスト
- タイムライン初期化テスト
- 応答可否判断テスト

### 3. NextTurnLogicTestCase (`tests/test_next_turn_logic.py`)

ターン管理ロジックのテスト：

- 複数エンティティでの連続的な会話進行テスト
- 複数ターンにわたるシステム状態変化テスト

## 会話フローのシーケンス図

現在のシステムでは、テキスト入力処理とターン進行は独立した2つの処理として実装されています。以下の2つのシーケンス図でそれぞれの流れを説明します。

### 1. テキスト入力処理のフロー

```mermaid
sequenceDiagram
    actor User as ユーザー
    participant View as IndexView
    participant IP as InputProcessor
    participant DB as データベース

    User->>View: テキストフォームから<br>メッセージ入力
    View->>View: form_valid(form)
    View->>IP: process_input(user_input)

    activate IP
    Note over IP: 入力処理開始
    IP->>IP: _static_guardrails(user_input)<br>（禁止ワード、文字数制限など）
    alt 静的ガードレールでブロック
        IP-->>View: ブロックメッセージ
    else 静的ガードレール通過
        alt OpenAI Moderation有効時
            IP->>IP: _dynamic_guardrails(user_input)<br>（OpenAI Moderation API）
            alt 動的ガードレールでブロック
                IP-->>View: ブロックメッセージ
            end
        end

        alt いずれかのガードレールでブロック
            View-->>User: エラーメッセージ表示
        else 全ガードレール通過
            Note over IP: 入力処理の実行<br>(将来的にSub-issueで改善予定)
            IP->>IP: _process_default(user_input)

            IP-->>View: 処理済みメッセージ
            View->>DB: Message.objects.create()<br>(DBに保存)
            View-->>User: 「メッセージが送信されました」
        end
    end
    deactivate IP
```

### 2. ターン進行処理のフロー

```mermaid
sequenceDiagram
    actor User as ユーザー
    participant NTV as NextTurnView
    participant CS as ConversationService
    participant SS as 特殊サービス<br>(GoogleMapsReviewService/RagService/NGWordService)
    participant IP as InputProcessor
    participant DB as データベース

    User->>NTV: 「1単位時間進める」<br>ボタンをクリック
    activate NTV
    Note over NTV: NextTurnView: process_next_turn()
    NTV->>CS: get_next_entity()

    activate CS
    CS->>DB: ActionTimeline取得
    Note over CS: ConversationService: 次のエンティティを決定
    CS->>SS: think(entity, context)

    alt can_respond = false
        Note over SS: 例: NGWordService: 禁止ワードチェック失敗
        SS-->>CS: False (応答不可)
        CS-->>NTV: ValueError
        NTV-->>User: エラーメッセージ
    else can_respond = true
        Note over SS: 例: NGWordService: 禁止ワードチェック通過
        SS-->>CS: True (応答可能)
        CS->>DB: ActionTimeline更新
        CS->>DB: ActionHistory作成/更新
        CS-->>NTV: entity

        NTV->>IP: process_input(dummy_text)
        IP-->>NTV: 応答テキスト
        NTV->>DB: Message.objects.create()<br>(AIメッセージ保存)
        NTV-->>User: インデックスページに<br>リダイレクト
    end
    deactivate CS
    deactivate NTV
```

## システムの特徴

このシステムは以下の特徴を持っています：

1. **安全性重視の設計**
    - 多層的なガードレール機能により、危険な入力や不適切なコンテンツをブロック
    - 静的チェックと動的チェックの組み合わせによる効率的な処理
    - セキュリティ対策（XSS対策、入力サニタイゼーション）の実装

2. **エンティティごとのカスタマイズ**
    - エンティティごとに異なるガードレール設定が可能
    - 特性に合わせた応答生成メカニズム

3. **堅牢なエラーハンドリング**
    - 外部API障害時のフォールバック処理
    - 例外発生時のグレースフルな対応

4. **多言語・Unicode対応**
    - 日本語を含む多言語テキスト処理
    - 絵文字や特殊文字のサポート

現在のシステムでは、テキスト入力処理とターン進行処理は2つの独立したプロセスとして実装されています：

1. **テキスト入力処理（IndexView経由）**
    - ユーザーがテキストフォームからメッセージを入力
    - InputProcessorがガードレール処理
    - メッセージがDBに保存される
    - **重要**: この処理ではターンは進行しない

2. **ターン進行処理（NextTurnView経由）**
    - ユーザーが「1単位時間進める」ボタンをクリック
    - ConversationServiceが次のエンティティを決定
    - 特殊サービスがエンティティの応答可否を判定
    - エンティティが応答可能な場合、ダミーテキストでメッセージが生成され、ターンが進行

この設計により、テキスト入力とターン進行が分離されているため：

- ユーザーは何度でもテキスト入力できるが、ターンは手動で進める必要がある
- NGWordServiceなどの特殊サービスは、ターン進行時にのみチェックされる
- InputProcessorのガードレールとConversationServiceの特殊サービスは別々のタイミングで実行される

現在、これらの2つのプロセスを統合する改善が計画されています（Sub-issue #6）。

## ライセンス

[ライセンス情報をここに記載]
