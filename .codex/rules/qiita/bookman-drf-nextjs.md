---
apply: "docs/qiita/bookman_drf_nextjs.md"
---

# 編集ルール（スタイルガイド） — Bookman DRF + Next.js

適用対象: docs/qiita/bookman_drf_nextjs.md（このファイル専用）

目的:
- 図書管理システム（bookman_backend / bookman_nextjs）の実装変更と Qiita 記事を同期する。
- backend / frontend のどちらに由来する記事変更かを追えるようにする。

適用スコープ:
- Qiita 記事「Django-rest-frameworkとNextJSで図書管理システムを作ってみる」
- bookman_backend と bookman_nextjs のセットアップ、実装手順、検証手順

## ルール

1) 実装差分との同期
   - bookman_backend または bookman_nextjs の関連箇所を修正した場合は、記事に影響する説明・コード例・検証手順を同じ粒度で更新する。
   - 2つのリポジトリにまたがる内容でも、記事管理ファイルは `docs/qiita/bookman_drf_nextjs.md` ひとつにまとめる。

2) 実装との整合性
   - 業務要件、画面の意味、API 契約を記事側だけで変えない。
   - 実装で未対応の TODO は、完了扱いに書き換えない。

3) リポジトリ分割の前提
   - `portfolio`, `bookman_backend`, `bookman_nextjs` は同じ親フォルダにある前提で扱う。
   - `.codex` の運用ルールは portfolio の `.codex` を一元管理元とし、Bookman の2リポジトリはそれを参照する前提で記述する。

4) コードブロックの表記
   - コンソール操作は `console:console` または既存記事の表記に合わせ、同一セクション内で表記ゆれを増やさない。
   - ファイル内容や差分は、言語タグのコロン右側に対象ファイル名を残す。

## チェックリスト（レビュー用）
- backend / frontend のどちらの差分に対応する記事更新か明記されているか。
- `docs/qiita/bookman_drf_nextjs.md` のコード例が実装差分と矛盾していないか。
- 記事内の TODO と GitHub Issue の粒度が食い違っていないか。
- `.codex` 参照運用の前提が、Bookman 2リポジトリにまたがる作業で破綻していないか。
