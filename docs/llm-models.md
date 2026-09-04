# LLMモデル設定

## 方針

本番のテキスト生成モデルは `lib/llm/valueobject/config.py` の
`ModelDefaults` から参照する。用途ごとに品質・コスト・遅延の優先度を分け、
全アプリを同じモデルへ一括置換しない。

GPT-5.6系のAPI仕様は、OpenAI公式ドキュメントで確認したモデルID・推論設定・
API経路を前提とする。
`gpt-5.6`エイリアスはSolへルーティングされるため、用途別既定値では
ルーティング先を明示する`gpt-5.6-sol`/`terra`/`luna`を使用する。

- [GPT-5.6モデルガイド](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6)
- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
- [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)

## モデル一覧

| モデル | 主な用途 | 採用理由 | API・設定 |
| --- | --- | --- | --- |
| `gpt-5.6-sol` | Tool選択を伴うAgent | 推論品質を優先 | Agents SDK / Responses、`low` |
| `gpt-5.6-terra` | 通常チャット、RAG、MSCI、Taxonomy、なぞなぞ | 品質とコストのバランス | Chat Completions、reasoning未指定 |
| `gpt-5.6-luna` | Kokkaiシナリオ、ストリーミング、レビュー分析 | 低コスト・大量処理・低遅延を優先 | Chat Completions、Kokkaiのみ`low` |

画像・音声・Embeddingはテキストモデルとは別用途であり、今回変更しない。

- 画像: `gpt-image-1-mini`
- 音声合成: `tts-1`
- 音声認識: `whisper-1`
- Embedding: `text-embedding-3-small`

## 用途別既定値

| 用途 | 共通設定 | 保存経路 |
| --- | --- | --- |
| Kokkai概要・選択肢 | `KOKKAI_SCENARIO` / Luna | `MeetingScenario.generator_model` |
| MSCIレポート要約 | `USA_RESEARCH` / Terra | `MsciCountryWeightReport.model_name` |
| 通常チャット | `LLM_CHAT` / Terra | `ChatLogs.model_name` |
| なぞなぞ | `LLM_RIDDLE` / Terra | `ChatLogs.model_name` |
| ストリーミング | `LLM_STREAMING` / Luna | `ChatLogs.model_name` |
| PDF RAG | `LLM_RAG` / Terra | `ChatLogs.model_name` |
| 六戸町会議録RAG | `ROKUNOHE_MINUTES_RAG` / Terra | `ChatLogs.model_name` |
| Google Mapsレビュー | `SHOPPING_REVIEW` / Luna | 分析結果の`model_name` |
| Taxonomy候補 | `TAXONOMY_CANDIDATE` / Terra | `llm_note` |
| Agent | `AI_AGENT` / Sol | Agents SDKの実行設定 |

`OpenAIGptConfig.from_profile` はChat Completions用プロファイルだけを受け付ける。
JSONが必要なKokkai生成では、共通サービスへ `response_format=json_object` を渡し、
Kokkaiプロファイルの `reasoning_effort=low` も同じリクエストへ渡す。

## 履歴と切り替え

既存のChatLogs、MeetingScenario、レビュー分析、Taxonomy候補のモデル名は変更しない。
切り替え後の新規呼び出しだけがGPT-5.6系を使用し、保存されるモデル名は実際に
リクエストへ渡したモデルIDと一致させる。MSCIレポートは過去レコードを更新せず、
今回追加したnullableの `model_name` へ新規生成分だけを記録する。

## 評価手順

同じプロンプトバージョン・同じ入力・同じ制約で、候補モデルを比較する。

1. Kokkaiの同一会議録について、概要生成と選択肢生成をLuna/Terra/Solで実行する。
2. JSON/structured output遵守率、根拠発言との一致、選択肢制約違反数を記録する。
3. 入力・出力トークン数、レイテンシ、API費用を記録する。
4. APIキー未設定、権限不足、非対応モデル、429発生時の表示を確認する。

開発環境では課金を伴う実API比較を自動実行しない。固定入力を用いたモックテストと、
モデル設定・JSON要求・保存モデル名の整合性を自動テストで確認し、実データの品質・
コスト・レイテンシ比較はAPIキーと評価対象データを用意した環境で実施する。
