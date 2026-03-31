# scripts

データの初期投入・バッチ実行など、手順化したスクリプトをまとめるフォルダです。

## 実行フロー（推奨）

DBをリセットしてデータを完全に再構築する場合、以下の **Step 1 → Step 2** の順序で実行してください。

### Step 1: `step1_industry_backup` (バックアップ)

DBをリセットする際、消えては困る実データ（`vnm.industry`）を保護します。

1. `step1_industry_backup.ps1` (Windows) または `.sh` (Linux) を実行します。
2. バックアップ取得後、スクリプトが待機状態になります。
3. 別のターミナル等で `python manage.py migrate` を実行し、DBをリセットします。
4. 元のスクリプトに戻り、Enter を押すと退避していたデータが復元されます。
    - ※ 不要な場合は Ctrl+C で中断してください。

### Step 2: `step2_import_data` (Seeder / 初期データ投入)

空のDBに対し、アプリ動作に必要なマスタデータや初期設定を一括投入します。

1. `step2_import_data.ps1` (Windows) または `.sh` (Linux) を実行します。
2. 各アプリの Fixture ロードと初期バッチが順番に実行されます。
    - ※ このスクリプト内でダミーデータ生成 (`generate_industry_dummy_data`) も行われます。Step 1
      で復元したデータがある場合は上書きに注意してください。

---

## 各スクリプトの詳細

### 1. Step 1: バックアップ

- **Windows (PowerShell)**: `step1_industry_backup.ps1`
- **Linux (bash)**: `step1_industry_backup.sh`

**実行例 (Windows):**

```powershell
.\scripts\step1_industry_backup.ps1
```

**環境変数（任意）:**

- `DB_NAME` (default: `portfolio_db`)
- `TABLE_NAME` (default: `vietnam_research_industry`)
- `BACKUP_DIR` (default: `./scripts/backups`)
- `MY_CNF` (default: `./scripts/.my.cnf`)
- `RESET_CMD`: 指定すると待機せずに自動でリセットコマンドを実行します。

### MySQL 認証設定 (推奨)

スクリプトがパスワード入力なしで動作するように、設定ファイル (`.my.cnf` または `my.ini`) を用意してください。
プロジェクトごとの設定として管理したい場合は、`scripts/.my.cnf` に配置することを推奨します（スクリプトはこのファイルを優先的に探します）。

**scripts/.my.cnf の作成例:**

```ini
[client]
user = YOUR_USERNAME
password = YOUR_PASSWORD
host = localhost
```

※ PowerShellで `scripts/.my.cnf` を作成する例:

```powershell
$content = "[client]`r`nuser=YOUR_USERNAME`r`npassword=YOUR_PASSWORD`r`nhost=localhost"
Set-Content -Path "scripts\.my.cnf" -Value $content -Encoding ASCII
```

※ 注意: `scripts/.my.cnf` を作成した場合は、セキュリティのため Git の管理対象から除外（`.gitignore` への追加）を推奨します。

---

### 2. Step 2: インポート (Seeder)

- **Windows (PowerShell)**: `step2_import_data.ps1`
- **Linux (bash)**: `step2_import_data.sh`

**実行例 (Windows):**

```powershell
.\scripts\step2_import_data.ps1
```

- **注**: `auth_user` (ID 1) が存在しない場合、スクリプト実行中に一時停止して作成を促します。
  多くの Fixture が `user_id: 1` に依存しているため、必ず ID 1 のスーパーユーザーを作成してください。
  別のターミナルで `python manage.py createsuperuser` を行い、ユーザー作成後に Enter で続行してください。

**インポートの順序:**

1. **Vietnam Research (Fixtures)**: マスタ・調査データ
2. **Vietnam Research (Batches)**: 市場データ・個別株・分析用データ生成
3. **GMarker / Shopping / Rental Shop**: 店舗・ユーザー・商品マスタ
4. **Soil Analysis**: 気象コード・天気予報バッチ・診断結果
5. **Taxonomy**: 生物分類体系・卵管理
6. **Hospital / AI Agent**: 施設・市区町村・AI設定
7. **USA Research**: 市場・財務・資産クラス長期推移 (1950年〜)
8. **Bank**: 銀行サマリーマスタ
