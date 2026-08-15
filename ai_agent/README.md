# AI Agent Skill Chain Game

`ai_agent` は、プレイヤーのセリフを OpenAI Agents SDK の Agent が解釈し、必要な Skill Tool を選んで実行する小さなゲームです。

## ドメイン

- 3x3 の盤面にプレイヤーと6つの問題駒を配置する
- 問題は単一教科、または国語×算数・国語×理科・算数×理科の科目横断に対応する
- プレイヤーは問題駒とプリセットセリフを選択する
- 成功した Skill は問題にダメージを与え、経験値を加算する
- 失敗した Skill は結果を残すが、問題と経験値は変更しない
- Agentの説明、選んだSkill、加工内容、結果、状態変化を実行履歴に残す

ゲーム状態は `GameState` の不変スナップショットで表し、`GameService` が選択とSkill適用を担当します。DBモデルや固定ターン制の履歴は使用しません。

## Skill Tool

Agentには、以下の6個のFunction Toolを登録します。UI表示名と実装名は `SkillToolCatalog` で対応付けます。

| 教科 | 表示名 | Function Tool名 |
| --- | --- | --- |
| 国語 | 読解分析 | `analyze_reading` |
| 国語 | 表現分析 | `analyze_expression` |
| 算数 | 計算 | `calculate` |
| 算数 | 数量比較 | `compare_quantities` |
| 理科 | 原因推論 | `infer_cause` |
| 理科 | 観察分析 | `analyze_observation` |

各Toolは `target_issue_id` を構造化された入力として受け取り、成功・失敗、ダメージ、獲得経験値、問題の残りHPを構造化された辞書で返します。Toolの呼び出し順は画面側で固定せず、Agentが結果を見て次のToolを選択します。

## 主なクラス

- `GameState`: 盤面、問題、経験値、選択状態、Tool履歴、Agent実行履歴のスナップショット
- `GameService`: ゲーム状態の生成、問題・セリフ選択、Skill適用
- `SkillToolCatalog`: Toolの実装名、表示名、教科、効果の定義
- `GameToolSet`: ドメインサービスを SDK Function Tool に変換するアダプター
- `GameAgentService`: 6個のToolをAgent実行基盤へ登録するサービス
- `AgentExecutionService`: Agentの実行結果とTool履歴を構造化するサービス

## テスト

```bash
python manage.py test ai_agent
```

ドメインテストでは、初期盤面、問題・セリフ選択、単一Toolの成功・失敗、異なる順番のTool Chain、教科と問題の不一致、表示名と実装名の対応、SDK Function Tool登録を検証します。
