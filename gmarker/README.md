# gmarker - Google Maps 連携アプリケーション

## 概要

gmarkerは、Google Maps PlatformのAPIを活用した位置情報サービスアプリケーションです。特定の地点を中心に、周辺のレストランやホテルなどの情報を検索・表示し、それらの場所に関するレビュー情報も閲覧できます。

## 主な機能

- 指定した座標を中心とした地図の表示
- 半径1500m以内の特定カテゴリ（レストラン、ホテルなど）の検索と表示
- 場所に関するレビュー情報の表示と管理

## データモデル

- **Place**: 基本的な場所情報（Google Place ID、名前、位置、評価など）
- **NearbyPlace**: 近隣の場所情報（カテゴリと検索タイプを含む）
- **PlaceReview**: 場所に対するレビュー情報

## Google Cloud Platform (GCP) 設定における注意点

### APIキー制限に関する重要な問題

Google Maps PlatformのAPIを使用する際、特にMaps JavaScript APIとPlaces API (New)を併用する場合、APIキーの制限設定に注意が必要です。

#### 問題の症状

- 地図が表示されない
- 403 Forbidden エラーが発生する
- APIキーの制限を解除すると正常に動作する

#### 原因

Google Maps PlatformのAPIは、その性質によって適切な制限方法が異なります：

- **Maps JavaScript API**：クライアントサイド（ブラウザ）で実行されるため、**HTTPリファラー制限**が適切
- **Places API (New)**：特に`places:searchNearby`エンドポイントはウェブサービスリクエストとして扱われるため、**IPアドレス制限
  **が必要

#### 解決策

1. **APIキーを2つ用意する**
    - Places API (New) 用のキー：サーバーのIPアドレス制限を設定（`GOOGLE_MAPS_BE_API_KEY`）
    - Maps JavaScript API と Directions API 用のキー：ウェブサイト（HTTPリファラー）制限を設定（`GOOGLE_MAPS_FE_API_KEY`）

2. **それぞれのAPIキーに適切な制限を設定する**
    - Places API用: 使用するサーバーのグローバルIPアドレスを制限に追加
    - Maps JavaScript API と Directions API用: 以下のようなHTTPリファラー制限を設定
      ```
      https://www.example.com/gmarker/*
      http://127.0.0.1:8000/*  # 開発環境用
      ```

#### Google Cloud サポートからの回答

GCP技術サポートからの回答では、Places API (New)
は一般的にウェブサービスリクエストとして扱われるため、HTTPリファラー制限ではなくIPアドレス制限を使用すべきと指摘されました。異なるAPIの性質に合わせて、複数のAPIキーを使い分けることが推奨されています。

## 利用方法

1. 中心座標を設定
2. カテゴリ（レストラン、ホテルなど）を選択
3. 検索結果が地図上に表示され、関連するレビュー情報も表示されます

## 開発者向け情報

開発時には、上記のGCP設定の注意点に留意してください。特に、APIキーの制限設定が不適切な場合、アプリケーションが正常に動作しないことがあります。

### 環境変数

アプリケーションでは以下の環境変数を使い分けています：

- `GOOGLE_MAPS_FE_API_KEY`: フロントエンド（ブラウザ）で使用するAPIキーにはHTTPリファラー制限を設定
    - Maps JavaScript API
    - Directions API

- `GOOGLE_MAPS_BE_API_KEY`: バックエンド（サーバー）で使用するAPIキーにはIPアドレス制限を設定
    - Places API (New)

### 実装上の注意

- バックエンドのPythonコードでは `GOOGLE_MAPS_BE_API_KEY` を使用する
- フロントエンドのJavaScriptコードでは `GOOGLE_MAPS_FE_API_KEY` を使用する
- テンプレート内でAPIキーを渡す際は、目的に応じて適切なキーを選択する

## 必要な環境変数

```
GOOGLE_MAPS_FE_API_KEY=フロントエンド用APIキー
GOOGLE_MAPS_BE_API_KEY=バックエンド用APIキー
GOOGLE_MAPS_MAP_ID=マップID
```

### Map ID

`GOOGLE_MAPS_MAP_ID`は地図のスタイルや特定の機能を有効にするためのIDです。このIDは単なる設定項目の識別子ではなく、Google
Cloud Platform上で作成・管理される地図の「スタイル設定パッケージ」を指定するための固有識別子です。

Map IDを使用することで以下が可能になります：

- カスタマイズされた地図スタイル（色、ラベル、地形表示など）の適用
- Advanced Markersなどの高度なGoogleマップ機能の有効化
- 地図表示の一貫性の確保

Google Cloud Platformのコンソールで「マップ管理」から作成できます。

## トラブルシューティング

### Advanced Markers に関する問題

Google Maps APIのv3.56以降では、Advanced Markersを使用するためにMap IDが必要になりました。以下の点を確認してください：

1. 有効なMap IDが設定されていること
2. Google Cloud Platformで作成したMap IDが環境変数`GOOGLE_MAPS_MAP_ID`に設定されていること
3. APIキーに「Maps JavaScript API」が有効化されていること
4. スクリプト読み込みに`libraries=marker`パラメータが含まれていること

### マーカーが表示されない問題

マップは表示されるがマーカーが表示されない場合は、以下を確認してください：

1. ブラウザのコンソールでエラーメッセージを確認する
2. ブラウザのネットワークタブでAPIリクエストのレスポンスを確認する
3. データソースの問題を確認する：
    - データベースにPlaceとNearbyPlaceのレコードが存在するか
    - APIキーにPlaces APIの権限が付与されているか
    - Google Cloud Platform上でAPIの利用制限（クォータ）に達していないか