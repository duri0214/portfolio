# Portfolio

Django(Python)を用いた、各種データ分析・可視化ツールのポートフォリオです。

![Python 3.12](https://img.shields.io/badge/python-3.12-green)
![Django 6.0](https://img.shields.io/badge/django-6.0-green)
![MySQL 8.0](https://img.shields.io/badge/mysql-8.0-green)

---

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
deactivate
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### データベースの構築 (Migration)
```bash
# データベースのマイグレーション
python manage.py migrate

# ※開発時（モデル変更時）のみ実行
# python manage.py makemigrations vietnam_research gmarker shopping linebot_engine rental_shop taxonomy soil_analysis securities hospital llm_chat ai_agent jp_stocks welfare_services
```

---

## 2. 初期データ投入 (Fixture & Initial Batches)

データの実行順序は重要です。以下の手順に従って投入してください。

### スーパーユーザーの作成
```bash
python manage.py createsuperuser
# ※ ID '1' のユーザーを作成してください
# （vietnam_research や shopping 等の一部の fixture が、作成者/管理者として user_id: 1 に依存しています）
```

### データのインポート手順
各アプリの Fixture と初期化バッチを、以下の順序で実行してください。
※ 備忘録：配布用 fixture (*/user.json) のパスワード実体は test#1234 です
※ サーバ（Ubuntu/Linux）で実行する場合は、パス区切り文字の `\` を `/` に置換して実行してください。

```bash
# --- Vietnam Research ---
python manage.py loaddata vietnam_research\fixtures\group.json
python manage.py loaddata vietnam_research\fixtures\indClass.json
python manage.py loaddata vietnam_research\fixtures\market.json
python manage.py loaddata vietnam_research\fixtures\symbol.json
python manage.py loaddata vietnam_research\fixtures\sbi.json
python manage.py loaddata vietnam_research\fixtures\unit.json
python manage.py loaddata vietnam_research\fixtures\vnIndex.json
python manage.py loaddata vietnam_research\fixtures\articles.json
python manage.py loaddata vietnam_research\fixtures\basicInformation.json
python manage.py loaddata vietnam_research\fixtures\financialResultWatch.json
python manage.py loaddata vietnam_research\fixtures\watchlist.json

# ここで vietnam_research の 各種データインポートバッチをまわす
python manage.py daily_import_market_data
python manage.py daily_import_from_sbi
python manage.py daily_import_from_vietkabu

# 分析用データ生成・チャート作成
# ※ --clear は初期データ用です。移行などで既にデータがある場合は実行不要です。
python manage.py generate_industry_dummy_data --clear
python manage.py daily_industry_chart_and_uptrend
python manage.py daily_industry_stacked_bar_chart

# FAO 水産物供給量グラフ / ベトナム統計局 経済指標
python manage.py monthly_fao_food_balance_chart
python manage.py monthly_vietnam_statistics

# --- GMarker ---
python manage.py loaddata gmarker\fixtures\place.json
python manage.py loaddata gmarker\fixtures\nearbyPlace.json

# --- Shopping ---
python manage.py loaddata shopping\fixtures\store.json
python manage.py loaddata shopping\fixtures\staff.json
python manage.py loaddata shopping\fixtures\product.json

# --- Rental Shop (Warehouse) ---
python manage.py loaddata rental_shop\fixtures\warehouse.json
python manage.py loaddata rental_shop\fixtures\staff.json
python manage.py loaddata rental_shop\fixtures\rentalStatus.json
python manage.py loaddata rental_shop\fixtures\company.json
python manage.py loaddata rental_shop\fixtures\billingPerson.json
python manage.py loaddata rental_shop\fixtures\billingStatus.json
python manage.py loaddata rental_shop\fixtures\warehousestaff.json
python manage.py loaddata rental_shop\fixtures\item.json

# --- Soil Analysis ---
python manage.py loaddata soil_analysis\fixtures\user.json
python manage.py loaddata soil_analysis\fixtures\companycategory.json
python manage.py loaddata soil_analysis\fixtures\company.json
python manage.py loaddata soil_analysis\fixtures\crop.json
python manage.py loaddata soil_analysis\fixtures\land_block.json
python manage.py loaddata soil_analysis\fixtures\land_period.json
python manage.py loaddata soil_analysis\fixtures\cultivationtype.json

# ここで soil analysis の master data バッチをまわす
python manage.py weather_load_const_master
python manage.py weather_generate_code_fixture_soil  # fixtureが変更されたときのみ実行
python manage.py weather_download_code_icon         # svgが変更されたときのみ実行

python manage.py loaddata soil_analysis\fixtures\jma_weather_code.json
python manage.py loaddata soil_analysis\fixtures\land.json

# ここ以降で soil analysis の 気象データ取得バッチをまわす
python manage.py weather_fetch_forecast
python manage.py weather_fetch_warning

python manage.py loaddata soil_analysis\fixtures\samplingmethod.json
python manage.py loaddata soil_analysis\fixtures\samplingorder.json
python manage.py loaddata soil_analysis\fixtures\land_ledger.json
python manage.py loaddata soil_analysis\fixtures\land_review.json
python manage.py loaddata soil_analysis\fixtures\land_score_chemical.json
python manage.py loaddata soil_analysis\fixtures\device.json

# --- Taxonomy ---
python manage.py loaddata taxonomy\fixtures\kingdom.json
python manage.py loaddata taxonomy\fixtures\phylum.json
python manage.py loaddata taxonomy\fixtures\classification.json
python manage.py loaddata taxonomy\fixtures\family.json
python manage.py loaddata taxonomy\fixtures\genus.json
python manage.py loaddata taxonomy\fixtures\species.json
python manage.py loaddata taxonomy\fixtures\naturalMonument.json
python manage.py loaddata taxonomy\fixtures\tag.json
python manage.py loaddata taxonomy\fixtures\breed.json
python manage.py loaddata taxonomy\fixtures\breedTags.json
python manage.py loaddata taxonomy\fixtures\feedGroup.json
python manage.py loaddata taxonomy\fixtures\henGroup.json

# ここで taxonomy の master data バッチ（気象コード等）をまわす
python manage.py weather_generate_code_fixture_taxonomy

python manage.py loaddata taxonomy\fixtures\jma_weather_code.json
python manage.py loaddata taxonomy\fixtures\eggLedger.json

# --- Hospital / AI Agent ---
python manage.py loaddata hospital\fixtures\user.json
python manage.py loaddata hospital\fixtures\member.json
python manage.py loaddata hospital\fixtures\ward.json
python manage.py loaddata hospital\fixtures\city.json
python manage.py loaddata hospital\fixtures\election.json
python manage.py loaddata hospital\fixtures\userattribute.json
python manage.py loaddata hospital\fixtures\voteplace.json

python manage.py loaddata ai_agent\fixtures\entity.json
python manage.py loaddata ai_agent\fixtures\guardrail_config.json
python manage.py loaddata ai_agent\fixtures\rag_material.json

# --- USA Research ---
# 資産クラスの長期推移データの初期取得（超長期: 指数を含めると1950年代〜取得可能）
python manage.py monthly_update_historical_assets --start 1950-01-01
```

---

## 3. 本番サーバ メンテナンス手順

サーバ（Ubuntu + Apache）でのデプロイ・更新手順です。

**事前チェック:**
*   `.env` が作成済みであること（各アプリの `.env.example` を参考に作成）
*   データベースのマイグレーション (`python manage.py migrate`) が完了していること

### .env 運用ルール

#### 1. .env の役割整理
*   **.env.example** (ルート)
    *   Django本体や外部API（Google Maps, LINE, Stripe等）のキー定義。
*   **lib/jira/.env.example**
    *   Jira連携用の認証情報定義。
*   **lib/llm/.env.example**
    *   OpenAI/Gemini APIキー。
    *   **CHROMA_DB_PATH**: ベクトルDBの保存先。
        *   **注意事項**: 環境ごとに設定変更が必要です。本番（Linux）に Windows パス（`C:\...`）を持ち込まないよう、相対パス（`./chroma_db`）の使用を推奨します。パス設定は環境の責務であり、不整合を防ぐため各環境で適切に設定してください。
*   **lib/slack/.env.example**
    *   Slack通知用のWebhook URL等。

### 権限構成
- `ubuntu`: Git操作、`collectstatic` 実行（ソースコード管理・静的ファイル生成）
- `www-data`: Webサーバ実行ユーザー（`media/`, `media/logs/` への書き込み権限が必要）

### 更新コマンド
```bash
cd /var/www/html/portfolio

# 1. ソースコードの更新
# ※ git clean -fd により venv ディレクトリも削除されます
git fetch --prune origin
sudo git reset --hard origin/master
sudo git clean -fd

# 2. venv の再構築 (リセット)
# 依存関係の変更（requirements.txt の更新）に備え、venv を作り直します
python3 -m venv venv
source /var/www/html/portfolio/venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 3. 権限の一時調整（ubuntu ユーザーでの作業用）
sudo chown -R ubuntu:www-data /var/www/html/portfolio
sudo chmod -R 755 /var/www/html/portfolio

# 4. Django メンテナンス
python manage.py collectstatic --noinput
python manage.py clearsessions
python manage.py migrate

# 5. 書き込みディレクトリの権限設定
sudo chmod -R 775 /var/www/html/portfolio/media /var/www/html/portfolio/static

# 6. LLM/RAG 関連の権限設定 (ChromaDB)
# ※ 暫定的にプロジェクトルート配下で運用しますが、将来的に適切な永続化パスを検討してください
sudo mkdir -p /var/www/html/portfolio/chroma_db
sudo chown -R www-data:www-data /var/www/html/portfolio/chroma_db
sudo chmod -R 775 /var/www/html/portfolio/chroma_db

# 7. Matplotlib キャッシュディレクトリの設定
# ※ 共有サーバー環境での権限エラー（/var/www/.cache へのアクセス拒否）を回避するため、media配下に作成します
sudo mkdir -p /var/www/html/portfolio/media/matplotlib_cache
sudo chown -R www-data:www-data /var/www/html/portfolio/media/matplotlib_cache
sudo chmod -R 775 /var/www/html/portfolio/media/matplotlib_cache

# 8. サービスの再起動
sudo systemctl restart apache2
sudo tail -n 200 /var/log/apache2/error.log
```

---

## 4. 各アプリケーションの機能とバッチ

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
米国市場のマクロ指標、セクターローテーション、資産クラスの長期推移を可視化します。

- **主要バッチ:**
  - `update_macro_indicators`: ISM, US10Y, VIX等の取得
  - `update_sector_rotation`: セクター別騰落率とRS順位の計算
  - `monthly_update_historical_assets`: 資産クラス別（SPY, TLT等）の長期価格推移の取得
  - `monthly_update_msci_weights`: MSCI国別ウェイトレポートの要約取得
  - `fetch_usa_rss`: 米国投資関連のRSSフィード取得

### [soil_analysis] 土壌分析・気象予報
気象庁データに基づく予報と、土壌計測データの管理を行います。

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

---

## 開発メモ
- **CSVからFixtureへの変換:** `python manage.py convert_csv_to_fixture` を実行。
  - CSVファイルを `vietnam_research/management/commands/` 配下に配置します。
  - ファイル名は `アプリ名_モデル名.csv`（例: `hospital_cityGroup.csv`）とする必要があります。
- **GMarker IP制限:** `GOOGLE_MAPS_BE_API_KEY` の制限には、開発マシンのグローバルIPv6アドレス（例: `2001:db8::1`）を設定すること。