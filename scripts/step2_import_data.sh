#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f "manage.py" ]]; then
  echo "manage.py が見つかりません。リポジトリのルートで実行してください。" >&2
  exit 1
fi

if [[ -x ".venv/bin/python" ]]; then
  python_exe=".venv/bin/python"
else
  python_exe="python"
fi

if [[ "$python_exe" == "python" ]] && ! command -v python >/dev/null 2>&1; then
  echo "Python not found. Create .venv or add python to PATH." >&2
  exit 1
fi

# --- User Check (ID 1 is required for some fixtures) ---
while true; do
  user_exists=$("$python_exe" manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(id=1).exists())")
  if [[ "$user_exists" == *"True"* ]]; then
    break
  fi
  echo "----------------------------------------------------------------------"
  echo "ID 1 のユーザーが必要です。別のターミナルで次を実行してください。"
  echo ">> $python_exe manage.py createsuperuser"
  echo "ユーザー作成後、この画面でEnterを押すとSeederを再開します。"
  read -r -p "Enterで再確認、Ctrl+Cで中止: "
done

# --- Migrate ---
"$python_exe" manage.py migrate

# --- USA Research (Masters) ---
"$python_exe" manage.py loaddata \
    usa_research/fixtures/market.json \
    usa_research/fixtures/symbol.json \
    usa_research/fixtures/unit.json

# --- Vietnam Research ---
"$python_exe" manage.py loaddata \
    vietnam_research/fixtures/group.json \
    vietnam_research/fixtures/indClass.json \
    vietnam_research/fixtures/market.json \
    vietnam_research/fixtures/symbol.json \
    vietnam_research/fixtures/sbi.json \
    vietnam_research/fixtures/vnIndex.json \
    vietnam_research/fixtures/articles.json \
    vietnam_research/fixtures/basicInformation.json \
    vietnam_research/fixtures/watchlist.json

# ここで vietnam_research の 各種データインポートバッチをまわす
"$python_exe" manage.py daily_import_market_data
"$python_exe" manage.py daily_import_from_sbi
"$python_exe" manage.py daily_import_usa_from_sbi
"$python_exe" manage.py daily_import_from_vietkabu

# 分析用データ生成・チャート作成
# ※ --clear は初期データ用です。移行などで既にデータがある場合は実行不要です。
"$python_exe" manage.py generate_industry_dummy_data --clear
"$python_exe" manage.py daily_industry_chart_and_uptrend
"$python_exe" manage.py daily_industry_stacked_bar_chart

# FAO 水産物供給量グラフ / ベトナム統計局 経済指標
"$python_exe" manage.py monthly_fao_food_balance_chart
# ※相手先サーバ（ベトナム）の証明書がうまくなくて実行できないので、ダミーデータ生成コマンドを用意
# ※ --clear は初期データ用です。移行などで既にデータがある場合は実行不要です。
# python manage.py monthly_vietnam_statistics
"$python_exe" manage.py generate_vietnam_statistics_dummy_data --clear

# --- GMarker ---
"$python_exe" manage.py loaddata \
    gmarker/fixtures/place.json \
    gmarker/fixtures/nearbyPlace.json

# --- Shopping ---
"$python_exe" manage.py loaddata \
    shopping/fixtures/user.json \
    shopping/fixtures/store.json \
    shopping/fixtures/userattribute.json \
    shopping/fixtures/product.json

# --- Rental Shop (Warehouse) ---
"$python_exe" manage.py loaddata \
    rental_shop/fixtures/warehouse.json \
    rental_shop/fixtures/user.json \
    rental_shop/fixtures/userattribute.json \
    rental_shop/fixtures/rentalStatus.json \
    rental_shop/fixtures/company.json \
    rental_shop/fixtures/billingPerson.json \
    rental_shop/fixtures/billingStatus.json \
    rental_shop/fixtures/warehousestaff.json \
    rental_shop/fixtures/item.json

# --- Soil Analysis ---
"$python_exe" manage.py loaddata \
    soil_analysis/fixtures/user.json \
    soil_analysis/fixtures/userattribute.json \
    soil_analysis/fixtures/companycategory.json \
    soil_analysis/fixtures/company.json \
    soil_analysis/fixtures/land_block.json \
    soil_analysis/fixtures/land_period.json \
    soil_analysis/fixtures/cultivationtype.json

# ここで soil analysis の master data バッチをまわす
"$python_exe" manage.py weather_load_const_master

"$python_exe" manage.py loaddata soil_analysis/fixtures/jma_weather_code.json
"$python_exe" manage.py loaddata soil_analysis/fixtures/rokunohe_land_registry.json

"$python_exe" manage.py loaddata soil_analysis/fixtures/samplingmethod.json
"$python_exe" manage.py generate_prefecture_representative_fixtures

# ここ以降で soil analysis の 気象データ取得バッチをまわす
if ! "$python_exe" manage.py weather_fetch_forecast; then
    echo "WARNING: weather_fetch_forecast failed. JMA API may be temporarily unavailable; continuing import." >&2
fi
if ! "$python_exe" manage.py weather_fetch_warning; then
    echo "WARNING: weather_fetch_warning failed. JMA API may be temporarily unavailable; continuing import." >&2
fi

"$python_exe" manage.py loaddata soil_analysis/fixtures/samplingorder.json
"$python_exe" manage.py loaddata soil_analysis/fixtures/device.json

# --- Taxonomy ---
"$python_exe" manage.py seed_taxonomy_data

# --- Hospital ---
"$python_exe" manage.py loaddata \
    hospital/fixtures/user.json \
    hospital/fixtures/ward.json \
    hospital/fixtures/city.json \
    hospital/fixtures/election.json \
    hospital/fixtures/userattribute.json \
    hospital/fixtures/voteplace.json

# --- USA Research ---
"$python_exe" manage.py loaddata usa_research/fixtures/financial_results.json

# 資産クラスの長期推移データの初期取得（1980年以降）
"$python_exe" manage.py monthly_update_historical_assets --start 1980-01-01

# --- Bank ---
"$python_exe" manage.py loaddata bank/fixtures/mufg_summary_master.json
