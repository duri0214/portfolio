# AI Agent Skill Chain Game

`ai_agent` は、プレイヤーのプリセットセリフを OpenAI Agents SDK の Agent が解釈し、必要な Skill Tool を選んで実行する小さな Skill Chain 型ゲームです。Tool の順番は画面に固定せず、Agent が結果を受け取りながら決定します。

## 現在の実行フロー

1. プレイヤーが3x3盤面から未解決の問題を選ぶ。
2. プレイヤーがプリセットセリフを選ぶ。
3. `GameAgentService` が問題・セリフ・利用可能なToolをAgentへ渡す。
4. `AgentExecutionService` がAgentのTool選択、実行結果、最終レポートを収集する。
5. Tool結果に応じて問題HPと経験値を更新し、完了した実行を履歴へ追加する。
6. SSEでTool単位の進行状況を表示し、完了後は履歴を再表示・リプレイする。

盤面には単一教科の問題3つ、科目横断の問題3つ、経験値ボーナス、休憩のイベントマスがあります。ゲーム状態は不変な `GameState` として扱い、Djangoセッションへ保存します。ゲーム状態をDBモデルやCookieへ保存したり、任意のシェルを実行したりはしません。

## 安全性

`SafetyPolicy` は、Agentへ渡る4つの境界を同じルールで確認します。

| 境界 | 確認内容 | 違反時の扱い |
| --- | --- | --- |
| 入力 | 空入力、最大500文字、危険な命令やプロンプト操作 | 実行前に `BLOCKED` |
| Tool引数 | JSONオブジェクト、サイズ上限、危険な命令 | Toolを呼ばず `BLOCKED` |
| Tool結果 | JSON化、サイズ上限、危険な内容 | 結果を公開せず `BLOCKED` |
| 最終出力 | JSON化、サイズ上限、危険な内容 | 出力を公開せず `BLOCKED` |

ゲーム固有のTool引数では、存在する問題IDだけを受け付け、選択中の問題以外を対象にできないようにします。SDKのガードレールに加えて、テスト用Runnerから抽出した履歴も実行サービスで再検証します。OpenAI Moderation APIとの連携は #310、RAG検索は #324 の責務として扱い、このアプリの決定的なローカル検証とは分離します。

## Skill Tool

`SkillToolCatalog` が画面表示名と実装名を対応付け、6個のFunction ToolをAgentへ登録します。

| 教科 | 表示名 | Function Tool名 |
| --- | --- | --- |
| 国語 | 読解分析 | `analyze_reading` |
| 国語 | 表現分析 | `analyze_expression` |
| 算数 | 計算 | `calculate` |
| 算数 | 数量比較 | `compare_quantities` |
| 理科 | 原因推論 | `infer_cause` |
| 理科 | 観察分析 | `analyze_observation` |

各Toolは `target_mondai_id` を受け取り、成功・失敗、ダメージ、経験値、残りHPを構造化して返します。解決済みの問題へのTool実行は失敗として記録され、問題と経験値は変更されません。

プリセットセリフには教科別の代表Tool Chainを定義しています。これはAgentの実行順を強制する設定ではなく、代表シナリオをテストで評価するための期待値です。

## 実行履歴とリプレイ

1回の実行は、次の値として保持されます。

- `AgentRun`: 入力、実行ID、ターン上限、開始・終了時刻、状態
- `ToolCall`: Agentが選択したTool名、引数、実行順
- `ToolResult`: Toolの結果、成功/失敗、結果順
- `Report`: 最終出力、Tool履歴、ターン数、エラー

完了した履歴はページ再読み込み後もセッションから復元できます。画面の「履歴をリプレイ」は保存済みのTool履歴を順番にハイライトする表示機能で、AgentやToolを再実行してゲーム状態を二重に更新することはありません。

## 主なクラス

- `GameState`: 盤面、問題、イベント、選択状態、経験値、履歴のスナップショット
- `GameService`: 問題・イベント・セリフの選択とSkill適用
- `SkillToolCatalog`: Toolの実装名、表示名、教科、効果、代表Chainの定義
- `GameToolSet`: ドメインサービスをSDK Function Toolへ変換するアダプター
- `GameAgentService`: ゲーム用Agentの構成、履歴変換、代表Chain評価
- `AgentExecutionService`: Runner委譲、ガードレール、Tool trace、タイムアウト、ターン上限の構造化
- `SafetyPolicy`: 入力、Tool引数、Tool結果、最終出力の決定的な検証

## テスト

```bash
python manage.py test ai_agent
```

ドメインテストでは、盤面とイベント、単一Tool、複数Tool Chain、プリセットセリフの代表Chain、Tool引数の制約を確認します。Agent実行テストでは、成功、失敗、ガードレール遮断、タイムアウト、ターン上限、ストリーミング途中失敗を確認します。画面テストでは、SSE、セッション復元、履歴の再表示、リプレイ導線を確認します。
