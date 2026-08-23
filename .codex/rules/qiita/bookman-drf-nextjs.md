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

1) リポジトリをまたぐ記事管理
   - 2つのリポジトリにまたがる内容でも、記事管理ファイルは `docs/qiita/bookman_drf_nextjs.md` ひとつにまとめる。

2) リポジトリ分割の前提
   - `portfolio`, `bookman_backend`, `bookman_nextjs` は同じ親フォルダにある前提で扱う。
   - `.codex` の運用ルールは portfolio の `.codex` を一元管理元とし、Bookman の2リポジトリはそれを参照する前提で記述する。

## チェックリスト（レビュー用）
- backend / frontend のどちらの差分に対応する記事更新か明記されているか。
- `.codex` 参照運用の前提が、Bookman 2リポジトリにまたがる作業で破綻していないか。
