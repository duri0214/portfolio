# チケット：NASDAQ100構成銘柄更新バッチの不整合解消とデータソース刷新

## 1. 現状の課題

本番環境（Ubuntu）およびローカル環境において、NASDAQ100構成銘柄を取得するバッチ `monthly_update_nasdaq100_list`（現在は暫定的に
`daily_` にリネーム）が以下のエラーで失敗している。

```
Failed to fetch data from Slickcharts: 403 Client Error: Forbidden for url: https://www.slickcharts.com/nasdaq100
```

### 原因分析

- 従来のデータソースである `Slickcharts` が、スクレイピング（自動アクセス）に対してボット検知・遮断（HTTP 403
  Forbidden）を強化した。
- User-Agent の偽装等で一時的に回避できる可能性はあるが、サービス側の規約変更や継続的なブロックのリスクが高く、運用が不安定になっている。

## 2. 改善案

データソースを `Slickcharts` から **Wikipedia (English)** に変更し、バッチ処理の堅牢性を向上させる。

### なぜ Wikipedia なのか

1. **信頼性**: NASDAQ-100 の構成銘柄は Wikipedia 上で有志により極めて迅速かつ正確にメンテナンスされており、公式発表に近い鮮度が保たれている。
2. **技術的容易性**: Wikipedia のテーブル構造は `pandas.read_html` 等で標準的に取得可能であり、複雑なスクレイピングロジックを必要としない。
3. **持続可能性**: Wikipedia は情報のオープンアクセスを是としており、一般的なデータソースとして広く利用されている。

### 変更内容の詳細

1. **データソース刷新**: `usa_research/management/commands/daily_update_nasdaq100_list.py` 内の `fetch_from_slickcharts`
   を `fetch_from_wikipedia` に置き換える。
2. **リネームと運用変更**: バッチ名を `monthly_` から `daily_`
   に正式に変更し、MSCI更新バッチと同様に日次実行（cron）の対象とする。これにより、不定期な銘柄入れ替えも翌日には反映されるようになる。
3. **テンプレートの修正**: フロントエンドの「データがありません」メッセージを、新しいコマンド名
   `daily_update_nasdaq100_list` を案内するように修正する。

## 3. 実装・検証プラン

1. **[承認待ち]** 本改善案の承認。
2. 別ブランチ `fix/nasdaq100-slickcharts-403` にて、Wikipedia 取得ロジックを実装。
3. ローカル環境にてコマンドを実行し、101銘柄（Ticker/Company/Sector）が正常に取得されることを確認。
4. `index.html` および `README.md` の記述を更新。
5. プルリクエストを作成し、レビューを経て master へマージ。

## 4. 懸念点と対策

- **懸念**: Wikipedia の銘柄名（Company Name）が Slickcharts と微差がある可能性がある。
- **対策**: 主キーは `Ticker` (Symbol) で管理しているため、既存レコードとの重複は発生せず、`update_or_create`
  により名称のみが更新される。実用上の問題はない。
