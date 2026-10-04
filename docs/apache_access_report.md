# Apache アクセス傾向メール仕様

## 目的

Apache アクセスログから不審なアクセスの兆候を匿名化された件数として集計し、portfolio のスーパーユーザーが固定の管理者宛先へメール送信できるようにします。サーバーへログインせずに概況を確認できることを目的とし、攻撃や情報漏えいを確定判定する機能ではありません。

この仕様は #954 の非公開メール機能を対象とします。#987 の [公開ダッシュボード](apache_access_dashboard.md) は独立した固定サンプルを表示し、この非公開集計を参照しません。

## 構成

- `lib/apache_access/domain/service/access_log_aggregator.py` の `ApacheAccessLogAggregator` が直近24時間分のログを集計する。
- `lib/apache_access/domain/service/report_service.py` がApacheログを集計し、結果をメモリ上でメール送信する。
- `lib/apache_access/domain/valueobject/report.py` が集計値とドメイン例外を定義する。
- `lib/apache_access/domain/service/report_mail.py` の `ApacheAccessReportMailService` がメール本文を生成する。
- `lib/apache_access/domain/service/report_summary.py` の `ApacheAccessReportSummaryService` は、明示的に許可した匿名化集計値だけを OpenAI API へ渡し、管理者向けの参考要約を生成する。
- `lib/apache_access/report_service.py` が手動実行する集計 CLI の入口になる。
- `lib/apache_access/report_receiver.py` が共通ナビバーのPOSTを受け、集計結果を既存の `MailService` で送信して元ページへ結果を返す。
- `lib/apache_access/test_report_service.py` が集計、読み取り、送信、権限、Web 操作をテストする。
- `config/urls.py` は送信 URL を `lib/apache_access/report_receiver.py` へ接続するだけとする。
- Djangoアプリ、Djangoモデル、migration、専用画面は追加しない。
- `home` はコンテンツカタログの責務だけを持ち、この機能を担当しない。

## 集計項目

- 対象期間と生成時刻
- リクエスト総数
- 401、403、404、5xx の件数
- 失敗応答が発生した送信元数
- 一つの送信元へ集中した失敗応答の最大件数
- portfolio のログイン先へのリクエスト数
- 一つの送信元からのログイン先リクエストの最大件数
- 要注意パス候補への 2xx 件数
- 対象期間の前半・後半それぞれの失敗応答件数
- 解析できなかったログ行数

## 情報の扱い

- 送信元 IP は集中度の集計中だけ使用する。
- IP、URL、クエリ文字列、ログ行、詳細な外部エラー文をメールや画面へ保存・表示しない。
- GPT要約は `APACHE_ACCESS_GPT_ENABLED=True` のときだけ利用する。外部APIへ渡す値は対象期間、件数、比率、期間前後半の差分に限定し、生ログ由来の識別子や詳細なエラーを渡さない。
- GPT要約は送信操作ごとに最大1回だけ呼び出し、出力は250トークンまでとする。APIキー未設定・API失敗・要約の形式不備では、要約を省いて機械的な集計メールを送る。
- GPT要約は OpenAI API による参考情報として、対象期間と根拠になる匿名化集計値のそばに表示する。観測した数値と推測を分け、攻撃・情報漏えいの断定や自動遮断の判断は掲載しない。
- Web プロセスは Apache 生ログを読み取り専用で扱い、集計結果や生ログを保存しない。
- メール宛先はプロジェクトルート `.env` の `MAIL_SMTP_USER`（SMTP送信元と同じ運用メールボックス）で固定し、画面入力を受け付けない。

## 送信操作

- 共通ナビバーの操作はスーパーユーザーにだけ表示する。
- 送信 URL は POST と CSRF 保護を必須とし、サーバー側でもスーパーユーザー権限を確認する。
- 専用画面を作らず、処理後は操作元へ戻って結果を通知する。
- 送信操作ごとにその時点の直近24時間を集計する。

## 集計処理

Web プロセスがApacheログを読み取り専用で集計し、匿名化された件数をメール本文へ直接渡します。集計結果、送信状態、生ログの保存先は持ちません。

## エラー

- ログがない、ログ形式を解析できない、ログを読み取れない場合は成功扱いにしない。
- ログ読み取り、SMTP設定、送信失敗を区別して利用者へ通知する。
- 詳細な例外はサーバーログへ記録し、利用者向け通知には機密情報を含めない。

## 運用手順

`.env` の正確な配置場所、権限設定、手動集計、メール送信、障害確認の手順は [`lib/apache_access/README.md`](../lib/apache_access/README.md) を参照してください。
