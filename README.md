# Portfolio

Django(Python)を用いた、各種データ分析・可視化ツールのポートフォリオです。

![Python 3.12](https://img.shields.io/badge/python-3.12-green)
![Django 6.0](https://img.shields.io/badge/django-6.0-green)
![MySQL 8.0](https://img.shields.io/badge/mysql-8.0-green)

## 1. セットアップ

### 仮想環境 (venv) の構築

**Linux**

```bash
# 作成
python3 -m venv venv

# 有効化
source venv/bin/activate

# 依存関係のインストール
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**Windows (PowerShell)**

既に `(venv)` が表示されている場合や `venv` フォルダが存在する場合は、この作成手順ではなく「venv の再構築 (リセット)
」を実行してください。

```powershell
# 作成
python -m venv venv

# 有効化
.\venv\Scripts\activate

# 依存関係のインストール
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### venv の再構築 (リセット)

ライブラリの更新などで環境を初期化したい場合。

**Linux**

```bash
deactivate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
deactivate 2>$null
Remove-Item -Recurse -Force venv -ErrorAction SilentlyContinue
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## 2. 本番サーバ メンテナンス手順

サーバ（Ubuntu + Apache）でのデプロイ・更新手順です。

**事前チェック:**

* `.env` が作成済みであること（各アプリの `.env.example` を参考に作成）
* データベースのマイグレーション (`python manage.py migrate`) が完了していること

### .env 運用ルール

#### 1. .env の役割整理

* **.env.example** (ルート)
    * Django本体や外部API（Google Maps, LINE, Stripe等）のキー定義。
* **lib/jira/.env.example**
    * Jira連携用の認証情報定義。
* **lib/llm/.env.example**
    * OpenAI/Gemini APIキー。
    * **CHROMA_DB_PATH**: ベクトルDBの保存先。
        * **注意事項**: 環境ごとに設定変更が必要です。本番（Linux）に Windows パス（`C:\...`）を持ち込まないよう、相対パス（
          `./chroma_db`）の使用を推奨します。パス設定は環境の責務であり、不整合を防ぐため各環境で適切に設定してください。
* **lib/slack/.env.example**
    * Slack通知用のWebhook URL等。

### 権限構成

- `ubuntu`: Git操作、`collectstatic` 実行（ソースコード管理・静的ファイル生成）
- `www-data`: Webサーバ実行ユーザー（`media/`, `media/logs/` への書き込み権限が必要）

### 日常の更新コマンド

ソースコードを更新してデプロイする際の手順です。

#### 1. ソースコードの更新

```bash
cd /var/www/html/portfolio
git fetch --prune origin
git reset --hard origin/master
git clean -fd
```

#### 2. サーバーセットアップ (権限設定)

サーバー構築時、または権限エラーが発生した際に実行してください。
これにより、以降に生成されるファイルも自動的に適切な権限（ACL）を継承します。
`venv` は実行ファイルを含むため、一括 `chmod 664` の対象から除外します。

```bash
sudo chown -R ubuntu:www-data /var/www/html/portfolio
sudo find /var/www/html/portfolio -path /var/www/html/portfolio/venv -prune -o -type d -exec chmod 775 {} +
sudo find /var/www/html/portfolio -path /var/www/html/portfolio/venv -prune -o -type f -exec chmod 664 {} +
sudo chmod +x /var/www/html/portfolio/scripts/*.sh
sudo apt update && sudo apt install acl -y
sudo setfacl -R -d -m u:ubuntu:rwx /var/www/html/portfolio/media
sudo setfacl -R -d -m g:www-data:rwx /var/www/html/portfolio/media
sudo setfacl -R -d -m o::rx /var/www/html/portfolio/media
```

#### 3. venv の再構築 (リセット)

(ライブラリに変更がある場合のみでOK。通常は `pip install -r requirements.txt` のみ)

```bash
deactivate 2>/dev/null || true
rm -rf venv
python3 -m venv venv
```

#### 4. 環境の構築

```bash
source /var/www/html/portfolio/venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

#### 5. Django メンテナンス

```bash
python manage.py collectstatic --noinput
python manage.py clearsessions
python manage.py migrate
```

#### 6. スーパーユーザーの作成

```bash
python manage.py createsuperuser
# ※ ID '1' のユーザーを作成してください
# （vietnam_research 等の一部の fixture が、作成者/管理者として user_id: 1 に依存しています）
```

#### 7. データのインポート手順

各アプリの Fixture と初期化バッチを、以下の順序で実行してください。
※ 備忘録：配布用 fixture (*/user.json) のパスワード実体は test#1234 です

手動実行の代わりに、以下のスクリプトで一括実行できます。

**Windows (PowerShell)**

```powershell
.\scripts\step2_import_data.ps1
```

**Linux (bash)**

```bash
chmod +x scripts/step2_import_data.sh
./scripts/step2_import_data.sh
```

#### 8. サービスの再起動

```bash
sudo systemctl restart apache2
sudo tail -n 50 /var/log/apache2/error.log
```

## 3. 各アプリケーションの機能とバッチ

### [vietnam_research] ベトナム株価分析・統計

ベトナムの株価データや統計指標（FAO、経済指標）の可視化を行います。
各期間（14日、7日、3日）を遡り、すべての期間で株価が上昇傾向（回帰直線の傾きが正）であれば `passed` をインクリメントします。
時系列データが存在しない場合は画像が保存されません。

- **主要バッチ:**
    - `daily_import_market_data / sbi / vietkabu`: 各種データインポート
    - `generate_industry_dummy_data`: 分析用ダミーデータ生成
    - `daily_industry_chart_and_uptrend`: 上昇トレンド判定とチャート生成
    - `daily_industry_stacked_bar_chart`: 業種別積上棒グラフ生成
    - `monthly_fao_food_balance_chart`: 水産物供給量グラフ生成
    - `monthly_vietnam_statistics`: ベトナム統計局経済指標の取り込み

### [usa_research] 米国株・マクロ指標分析

米国市場のマクロ指標、セクターローテーション、資産クラスの長期推移を可視化し、広瀬隆雄氏の手法に基づく「決算ウォッチ」機能を備えています。

- **主要バッチ:**
    - `update_macro_indicators`: ISM, US10Y, VIX等の取得
    - `update_sector_rotation`: セクター別騰落率とRS順位の計算
    - `monthly_update_historical_assets`: 資産クラス別（SPY, TLT等）の長期価格推移の取得
    - `daily_update_msci_weights`: MSCI国別ウェイトレポートの要約取得
    - `fetch_usa_rss`: 米国投資関連のRSSフィード取得

### [soil_analysis] 土壌分析・気象予報

気象庁データに基づく予報と、土壌計測データの管理を行います。

- **ドメイン知識（圃場ブロック）:**
  圃場は 3x3 の 9ブロックで管理されます。計測器の配置やデータ構造は以下の通りです。
    ```text
    ┌────┬────┬────┐
    │ C3 │ B3 │ A3 │  (Row 3)
    ├────┼────┼────┤
    │ C2 │ B2 │ A2 │  (Row 2)
    ├────┼────┼────┤
    │ C1 │ B1 │ A1 │  (Row 1)
    └────┴────┴────┘
     (Col C) (Col B) (Col A)
    ```
    - 行（Row）: 1, 2, 3 / 列（Col）: A, B, C
    - 物理性（土壌硬度）は各ブロック単位で計測されます。
    - 化学分析は圃場（LandLedger）単位で管理されます。

- **テストデータ生成:**
  ```bash
  # 土壌硬度計測器のダミーCSV生成
  python manage.py hardness_generate_dummy_csv --num_fields 20
  ```

### [linebot_engine] LINE Bot 基盤

メッセージログの蓄積と健康チェック機能を備えたエンジン。

- [qiita記事：LINEからChatGPTと会話し、絵も描く](https://qiita.com/YoshitakaOkada/items/f51f52a8041439a1dbc9)

- **メンテナンス:**
  ```bash
  # 月次ログクリーンアップ
  python manage.py monthly_cleanup_linebot_engine
  ```

### [hospital] 不在者投票管理

病院内での不在者投票事務（名簿作成、選管への請求等）をサポートします。

### [bank] 銀行明細管理

MUFG普通預金のCSV（Eco通帳）アップロードおよび明細の集計・管理を行います。

- **テストデータ生成:**
  ```bash
  # MUFG普通預金のダミーデータ生成
  python manage.py generate_mufg_dummy_data --count 100
  ```

### [jp_stocks] 日本株板シミュレータ

`Order` モデルを用いた板情報の動的計算とマッチングシミュレーション。

## 開発メモ

- **CSVからFixtureへの変換:** `python manage.py convert_csv_to_fixture` を実行。
    - CSVファイルを `vietnam_research/management/commands/` 配下に配置します。
    - ファイル名は `アプリ名_モデル名.csv`（例: `hospital_cityGroup.csv`）とする必要があります。
- **GMarker IP制限:** `GOOGLE_MAPS_BE_API_KEY` の制限には、開発マシンのグローバルIPv6アドレス（例: `2001:db8::1`）を設定すること。
