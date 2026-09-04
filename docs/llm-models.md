# LLMモデル設定

## 方針

本番のテキスト生成モデルは `lib/llm/valueobject/config.py` の
`ModelDefaults.TEXT_MODEL` から参照する。Portfolioではモデル運用を単純にするため、
テキスト生成系の全用途を `gpt-5.6-luna` に統一する。用途別のプロファイル名は、
呼び出し箇所の責務とAPI・推論設定を識別するために残すが、モデルの分散には使わない。

GPT-5.6系のAPI仕様は、OpenAI公式ドキュメントで確認したモデルID・推論設定・
API経路を前提とする。
`gpt-5.6`エイリアスはSolへルーティングされるため、共通VOにはエイリアスと
Sol/Terra/Lunaの明示IDを定義する。現行の既定値はLunaのみを使う。

- [GPT-5.6モデルガイド](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6)
- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
- [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)

## モデル一覧

| モデル | Portfolioでの扱い | 採用理由 | API・設定 |
| --- | --- | --- | --- |
| `gpt-5.6-luna` | 全テキスト生成の現行モデル | 必要なAPI機能を備え、コストと運用を単純化できる | Chat Completions / Responses、必要箇所のみ`low` |
| `gpt-5.6-terra` | 共通VOに定義する比較・将来候補 | 型安全な選択肢として残し、将来の評価に利用できる | Chat Completions / Responses |
| `gpt-5.6-sol` | 共通VOに定義する比較・将来候補 | 型安全な選択肢として残し、将来の評価に利用できる | Chat Completions / Responses |

公式仕様上、LunaはChat CompletionsとResponses、Function calling、Structured outputs、
Streamingに対応する。AgentのTool利用を含め、既存の呼び出し経路を変更せずに統一できる。

画像・音声・Embeddingはテキストモデルとは別用途であり、今回変更しない。

- 画像: `gpt-image-1-mini`
- 音声合成: `tts-1`
- 音声認識: `whisper-1`
- Embedding: `text-embedding-3-small`

## 用途別既定値

| 用途 | 共通設定 | モデル | 保存経路 |
| --- | --- | --- | --- |
| Kokkai概要・選択肢 | `KOKKAI_SCENARIO`（`low`） | Luna | `MeetingScenario.generator_model` |
| MSCIレポート要約 | `USA_RESEARCH` | Luna | `MsciCountryWeightReport.model_name` |
| 通常チャット | `LLM_CHAT` | Luna | `ChatLogs.model_name` |
| なぞなぞ | `LLM_RIDDLE` | Luna | `ChatLogs.model_name` |
| ストリーミング | `LLM_STREAMING` | Luna | `ChatLogs.model_name` |
| PDF RAG | `LLM_RAG` | Luna | `ChatLogs.model_name` |
| 六戸町会議録RAG | `ROKUNOHE_MINUTES_RAG` | Luna | `ChatLogs.model_name` |
| Google Mapsレビュー | `SHOPPING_REVIEW` | Luna | 分析結果の`model_name` |
| Taxonomy候補 | `TAXONOMY_CANDIDATE` | Luna | `llm_note` |
| Agent（Responses） | `AI_AGENT`（`low`） | Luna | Agents SDKの実行設定 |

`OpenAIGptConfig.from_profile` はChat Completions用プロファイルだけを受け付ける。
JSONが必要なKokkai生成では、共通サービスへ `response_format=json_object` を渡し、
Kokkaiプロファイルの `reasoning_effort=low` も同じリクエストへ渡す。

## 型安全性と履歴

モデルIDは `OpenAiModel` の `Literal` と `ModelName` に定義し、実行時の共通設定は
`ModelDefaults` から参照する。現在のテキスト生成系アプリケーションコードにはモデルIDを直接書かず、
`ModelDefaults.TEXT_MODEL` または用途別プロファイルを利用する。

既存のChatLogs、MeetingScenario、レビュー分析、Taxonomy候補のモデル名は変更しない。
新規呼び出しだけをLunaへ切り替え、保存されるモデル名は実際にリクエストへ渡した
モデルIDと一致させる。MSCIレポートは過去レコードを更新せず、今回追加したnullableの
`model_name` へ新規生成分だけを記録する。

Sol/Terraや旧モデルの定義は、型安全な比較・履歴互換のために共通VOへ残すが、
現行の既定値やヘルスチェック対象には含めない。

## 評価手順

現行既定値はLunaに統一し、同じプロンプトバージョン・同じ入力・同じ制約で品質を確認する。
将来モデルを変更する場合に限り、Luna/Terra/Solの出力を同一入力で比較する。

1. 現行のLunaで、Kokkaiの同一会議録について概要生成と選択肢生成を実行する。
2. JSON/structured output遵守率、根拠発言との一致、選択肢制約違反数を記録する。
3. 入力・出力トークン数、レイテンシ、API費用を記録する。
4. APIキー未設定、権限不足、非対応モデル、429発生時の表示を確認する。

開発環境では課金を伴う実API比較を自動実行しない。固定入力を用いたモックテストと、
モデル設定・JSON要求・保存モデル名の整合性を自動テストで確認し、実データの品質・
コスト・レイテンシ比較はAPIキーと評価対象データを用意した環境で実施する。
