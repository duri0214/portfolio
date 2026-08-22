# Skill Chain型AI Agentを小さなゲームで検証する

このページでは、`ai_agent` アプリで実装している Skill Chain 型AI Agentの設計と、安全性・実行履歴・テストの考え方を説明します。

## この記事で扱うもの

プレイヤーは盤面上の問題とプリセットセリフを選び、Agentへ依頼します。Agentは6つのFunction Toolから必要なものを選び、Toolの結果を見て次のToolを追加するか、最終レポートを返します。画面はこの過程をSSEで受け取り、Toolの選択・開始・完了・失敗と最終レポートを表示します。

ソースコード:

<https://github.com/duri0214/portfolio/tree/master/ai_agent>

## 実行の流れ

```text
問題・セリフの選択
        ↓
GameAgentService が Agent と6つのToolを構成
        ↓
AgentExecutionService が Runner を実行
        ↓
Tool Call → Tool Result → 必要なら次のTool
        ↓
AgentRun / Report を作成
        ↓
SSE表示・セッション保存・履歴リプレイ
```

`GameService` は問題HP、経験値、イベントマスなどゲーム固有の状態だけを担当します。Agentの判断順は `GameService` に埋め込まず、`GameToolSet` を通じてAgentのTool呼び出し結果を適用します。

## 安全性を4つの境界で確認する

Agentの安全性を最終出力だけの問題にせず、次の境界ごとに扱います。

### 1. 入力

入力は文字列であること、500文字以内であること、シェル実行やプロンプト操作を示す危険な命令を含まないことを確認します。違反時はRunnerを呼ばず、`AgentRunStatus.BLOCKED` を返します。

### 2. Tool引数

Tool引数はJSONオブジェクトとして解釈でき、サイズ上限内であることを確認します。ゲームではさらに、Tool名と `target_mondai_id` が許可された値であること、選択中の問題だけを対象にしていることを検証します。

### 3. Tool結果

Tool結果はJSONとして扱えるサイズに制限し、危険な命令を含む結果をそのままAgentや画面へ渡しません。SDKのTool Output Guardrailと、`AgentExecutionService` が履歴を構造化する時点の再検証を併用しています。

### 4. 最終出力

最終出力もサイズと危険な内容を確認します。違反時は `Report.output` を公開せず、理由だけを `Report.error` に残します。

この決定的なローカル検証は、外部サービスの判定に依存しません。OpenAI Moderation APIの導入は #310、資料検索を行うRAG Toolの導入は #324 の責務とし、導入する場合もAgentが必要に応じて選択するToolとして追加します。

## Skill Chainと代表シナリオ

Toolの登録順や画面のボタン順を実行順として扱わず、Agentが結果を受けて次のToolを選べるようにしています。一方、テストではプリセットセリフごとの代表Chainを期待値として宣言し、実行された `ToolCall` の順番を評価できます。

例えば国語の問題では、次のような代表ケースを検証します。

- 「直接解決を試す」: `analyze_expression`
- 「条件を整理して解く」: `analyze_reading`
- 「別の観点で検証する」: `analyze_reading` → `analyze_expression`

算数・理科にも同じ考え方で教科別の代表Chainを用意しています。これはテスト用の評価基準であり、Agentへ順番を強制するプロンプトや分岐ではありません。

## 実行履歴を構造化する

1回の依頼を `AgentRun` としてまとめ、内部に次の履歴を持たせます。

- `ToolCall`: Tool名、構造化引数、呼び出し順
- `ToolResult`: Tool名、結果、成功/失敗、結果順
- `Report`: 最終出力、Tool履歴、ターン数、エラー

ゲーム画面用の `AgentExecutionRecord` は、この `AgentRun` に加えて問題名、セリフ、HP変化、経験値変化を保持します。これにより、単に「成功した」という通知だけでなく、どの入力に対してどのToolが選ばれ、どんな結果を経て最終出力に至ったかを後から確認できます。

保存先はDjangoセッションです。DBモデルやゲーム状態Cookieに依存せず、ページを再読み込みしても盤面と履歴を復元できます。履歴の「リプレイ」は保存済みのTool行を順番に画面上で再生するだけで、AgentやToolを再実行しません。したがって、リプレイによる経験値やHPの二重更新は起きません。

## 画面で確認できること

- 3x3盤面上のプレイヤー、6つの問題、経験値ボーナス、休憩
- 選択した問題とプリセットセリフ
- SSEによる `run.started`、`tool.selected`、`tool.started`、`tool.completed`、`tool.failed`、`report.completed`
- Toolごとの入力要約、結果要約、順番、HP、経験値
- `AgentRun`、`Tool Call`、`Tool Result`、`Report` の詳細
- 完了履歴の再表示とリプレイ

## テスト

```bash
python manage.py test ai_agent
```

テストでは、代表Chain、Toolの成功・失敗、選択中の問題以外への引数、入力・Tool入出力・最終出力のガードレール、タイムアウト、ターン上限、SSEの途中失敗、セッション復元と履歴リプレイ導線を確認します。

## 関連Issueの責務

- #908: 現行Skill Chain型Agentの安全性、実行履歴、代表Chainテスト、記事とREADMEの整合性
- #310: 外部Moderationを含む信号機型ガードレールの拡張
- #324: RAG・ベクトル検索をAgentの選択可能なToolとして導入する検討
