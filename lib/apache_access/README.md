# ApacheAccessReportService

`ApacheAccessReportService` は Apache のアクセスログを匿名化した件数へ集計し、既存の `MailService` で管理者へ送信する共通ライブラリです。Djangoアプリ、Djangoモデル、migrationには依存しません。

## 責務

- combined 形式の現行・ローテート済みアクセスログを直近24時間分集計する
- 集計中だけ送信元を使い、IP、URL、クエリ、ログ行を保持しない
- 匿名化済みの日時と件数だけを JSON に保存する
- JSON の鮮度と15分の送信間隔を確認する
- プレーンテキスト・HTML本文を作り、`MailService` に送信を依頼する

共通ナビバーの表示、POST・CSRF・スーパーユーザー確認、操作元へのリダイレクトは `config.views` が担当します。専用画面は作らず、`home` はこの処理を担当しません。

## 集計の単独実行

プロジェクトルートの `.env` を設定し、次を実行します。

```bash
python -m lib.apache_access.report_service
```

成功時は `Apache アクセス集計を保存しました。` と出力して終了コード0、失敗時は原因を出力して終了コード1を返します。詳細な本番手順は `docs/apache_access_report.md` を参照してください。
