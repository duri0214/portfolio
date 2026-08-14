---
apply: "docs/qiita/ai_agent.md"
---

# 編集ルール（スタイルガイド） — AI Agent

適用対象: `docs/qiita/ai_agent.md`

## 目的

- Qiita記事「（途中）AI Agent を試作する」を、原本の内容を保ちながらGitHubで継続管理する。
- `ai_agent/` の実装、関連Issue、記事の説明を対応付ける。
- Phase 2の大改修で、設計・実装・記事の内容が分離しないようにする。

## 適用スコープ

- 会話型マルチエージェントの概要とターン制処理
- RAG、ガードレール、会話履歴の説明
- Factory、Repository、Service、Value Objectの責務説明
- `ai_agent/` への参照、関連Issue、コード例の更新
- 非対象: Phase 1でのAI Agent実装の大幅な変更、未実装機能の完成扱い

## ルール

1) 原本の主題を維持する
   - 記事の入口は「ターン制で動く会話型マルチエージェントの試作」とする。
   - Factory、Repository、Service、Value Objectの説明は、マルチエージェントの処理と関連付ける。
   - 一般的なAI Agent論や、実装していない機能の解説へ広げすぎない。

2) 現在の実装と将来計画を分ける
   - 現在の処理は `ai_agent/` の実装を確認してから記述する。
   - ベクトル検索、動的モデレーション、未実装の外部連携は、実装済みと断定しない。
   - 改善途中の内容は、関連IssueまたはPhase 2への参照を付ける。

3) 1ターンの処理順を崩さない
   - 入力受付、ガードレール、ターン取得、文脈分析・RAG、履歴保存、次ターン取得の順で説明する。
   - `IndexView`、`InputProcessor`、`TurnManagement`、`ContextAnalyzer`、`ActionHistory`、`Message`の名称は実装と一致させる。
   - 処理を追加・変更した場合は、記事のライフサイクル説明と実装リンクを同時に確認する。

4) DDD層の責務を混ぜない
   - Factoryは生成、Repositoryはデータストアとの入出力、Serviceはシナリオ進行、Value Objectは意味と制約を担当する。
   - Repositoryに業務判断、Serviceに低レベルな永続化処理を追加したような説明にしない。
   - 層を追加して説明する場合は、既存のRepository・Service・Value Objectとの責務差分を明記する。

5) リンクを維持する
   - 記事原本、`ai_agent/` のソース、親Issue #902、Phase 1 #903、Phase 2 #904を参照できる状態にする。
   - ガードレールは #310、ベクトル検索RAGは #324を関連Issueとして扱う。
   - ブランチ固有のURLやローカルパスを記事に残さない。

6) コードブロックの表記を統一する
   - Pythonファイルは `python:ai_agent/domain/service/input_processor.py` のように対象ファイルを付ける。
   - コンソール操作は `bash:console` を使う。
   - 実装を確認していないコードを記事へ新規掲載しない。

7) Phaseごとの変更範囲を守る
   - Phase 1は原本のGitHub化と記事管理ルールの整備を中心とする。
   - Phase 2で実装や設計を大きく変えた場合は、変更後のコードと記事を同じPRで確認する。

## チェックリスト（レビュー用）

- Qiita原本の主題と説明順が維持されているか。
- 記事の処理フローが現行の `ai_agent/` と矛盾していないか。
- 実装済み、想定、改善途中の機能が区別されているか。
- Factory、Repository、Service、Value Objectの責務が混ざっていないか。
- `ActionHistory` と `Message` の保存・更新順が正しく説明されているか。
- #310、#324、#902、#903、#904へのリンクが有効か。
- コードブロックのファイルパスとタグが既存のQiita記事ルールに沿っているか。
- Phase 1の範囲を超える実装変更を混ぜていないか。
