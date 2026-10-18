# gmarker - Google Maps 連携アプリケーション

## 概要

gmarker は Google Maps Platform の API を使い、指定した中心地点の周辺店舗を地図とレビューで表示する Django アプリケーションです。レストランやホテルの検索に加え、候補検索 criteria に登録した店舗パターンを同じ画面で検索できます。

## 主な機能

- 指定した座標を中心にした地図表示
- レストラン、ホテルなどの Nearby Search
- Text Search と Nearby Search を組み合わせた候補店舗の抽出
- 店舗ごとの最大 5 件のレビュー表示
- criteria による候補検索パターンの追加

## 利用方法

1. 中心座標を設定します。
2. トップ画面でカテゴリまたは候補検索プロファイルを選びます。
3. 地図と店舗ごとのレビューを確認します。

候補検索プロファイルは [criteria/shibuya_craft_beer.json](criteria/shibuya_craft_beer.json) のような JSON ファイルで定義します。`gmarker/criteria/` にファイルを追加すると、ファイル内の `slug` と `label` が URL と画面ボタンに反映されます。候補抽出の共通コードを変更せず、次の項目をプロファイルごとに指定できます。

- `slug`、`label`、`area_name`
- 検索中心、半径、対象境界
- Text Search の検索語
- Nearby Search の type
- API の言語コードと地域コード
- type 検索だけで見つかった店舗を候補に含めるか
- 必要な場合だけ指定する必須店舗条件

`required_place` を省略したプロファイルでは、必須店舗の照合を行いません。候補画面には検索語、検索経路、type 判定などの検品情報を表示せず、店舗とレビューだけを表示します。

## Google Cloud Platform の設定

バックエンドから Places API (New) を呼び出すキーと、ブラウザから Maps JavaScript API を呼び出すキーを分けて設定します。

```powershell
$env:GOOGLE_MAPS_BE_API_KEY = "サーバー用 API キー"
$env:GOOGLE_MAPS_FE_API_KEY = "ブラウザ用 API キー"
$env:GOOGLE_MAPS_MAP_ID = "Google Maps の Map ID"
```

Places API のキーには Places API (New) の権限とサーバーの IP 制限を、フロントエンドのキーには Maps JavaScript API の権限と利用する HTTP リファラー制限を設定してください。

実行前に [Google Maps Platform 利用規約](https://mapsplatform.google.com/terms/) と [Places API のポリシー・帰属表示要件](https://developers.google.com/maps/documentation/places/web-service/policies) を確認してください。
