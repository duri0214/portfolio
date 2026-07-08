#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f "manage.py" ]]; then
  echo "manage.py が見つかりません。リポジトリのルートで実行してください。" >&2
  exit 1
fi

# --- User Check (ID 1 is required for many fixtures) ---
while true; do
    USER_EXISTS=$(python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(id=1).exists())")
    if [[ "$USER_EXISTS" == *"True"* ]]; then
        break
    fi
    echo "----------------------------------------------------------------------"
    echo "CRITICAL: Superuser with ID 1 not found."
    echo "Many fixtures (Vietnam Research, USA Research, etc.) depend on user_id 1."
    echo "Please create a superuser now in another terminal:"
    echo ">> python manage.py createsuperuser"
    echo "----------------------------------------------------------------------"
    echo "Press Enter AFTER creating the user to check again, or Ctrl+C to abort."
    read -r
done

# --- Migrate ---
python manage.py migrate

# --- USA Research (Masters) ---
python manage.py loaddata \
    usa_research/fixtures/market.json \
    usa_research/fixtures/symbol.json \
    usa_research/fixtures/unit.json

# --- Vietnam Research ---
python manage.py loaddata \
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
python manage.py daily_import_market_data
python manage.py daily_import_from_sbi
python manage.py daily_import_usa_from_sbi
python manage.py daily_import_from_vietkabu

# 分析用データ生成・チャート作成
# ※ --clear は初期データ用です。移行などで既にデータがある場合は実行不要です。
python manage.py generate_industry_dummy_data --clear
python manage.py daily_industry_chart_and_uptrend
python manage.py daily_industry_stacked_bar_chart

# FAO 水産物供給量グラフ / ベトナム統計局 経済指標
python manage.py monthly_fao_food_balance_chart
# ※相手先サーバ（ベトナム）の証明書がうまくなくて実行できないので、ダミーデータ生成コマンドを用意
# ※ --clear は初期データ用です。移行などで既にデータがある場合は実行不要です。
# python manage.py monthly_vietnam_statistics
python manage.py generate_vietnam_statistics_dummy_data --clear

# --- GMarker ---
python manage.py loaddata \
    gmarker/fixtures/place.json \
    gmarker/fixtures/nearbyPlace.json

# --- Shopping ---
python manage.py loaddata \
    shopping/fixtures/user.json \
    shopping/fixtures/store.json \
    shopping/fixtures/userattribute.json \
    shopping/fixtures/product.json

# --- Rental Shop (Warehouse) ---
python manage.py loaddata \
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
python manage.py loaddata \
    soil_analysis/fixtures/user.json \
    soil_analysis/fixtures/userattribute.json \
    soil_analysis/fixtures/companycategory.json \
    soil_analysis/fixtures/company.json \
    soil_analysis/fixtures/land_block.json \
    soil_analysis/fixtures/land_period.json \
    soil_analysis/fixtures/cultivationtype.json

# ここで soil analysis の master data バッチをまわす
python manage.py weather_load_const_master

python manage.py loaddata soil_analysis/fixtures/jma_weather_code.json
python manage.py loaddata soil_analysis/fixtures/rokunohe_land_registry.json

python manage.py loaddata soil_analysis/fixtures/samplingmethod.json
python manage.py generate_prefecture_representative_fixtures

# ここ以降で soil analysis の 気象データ取得バッチをまわす
if ! python manage.py weather_fetch_forecast; then
    echo "WARNING: weather_fetch_forecast failed. JMA API may be temporarily unavailable; continuing import." >&2
fi
if ! python manage.py weather_fetch_warning; then
    echo "WARNING: weather_fetch_warning failed. JMA API may be temporarily unavailable; continuing import." >&2
fi

python manage.py loaddata soil_analysis/fixtures/samplingorder.json
python manage.py loaddata soil_analysis/fixtures/device.json

# --- Taxonomy ---
python manage.py loaddata \
    taxonomy/fixtures/kingdom.json \
    taxonomy/fixtures/phylum.json \
    taxonomy/fixtures/classification.json \
    taxonomy/fixtures/family.json \
    taxonomy/fixtures/genus.json \
    taxonomy/fixtures/species.json \
    taxonomy/fixtures/naturalMonument.json \
    taxonomy/fixtures/tag.json \
    taxonomy/fixtures/breed.json \
    taxonomy/fixtures/breedTags.json \
    taxonomy/fixtures/feedGroup.json \
    taxonomy/fixtures/henGroup.json

# ここで taxonomy の master data バッチ（気象コード等）をまわす
python manage.py seed_taxonomy_animals
python manage.py loaddata taxonomy/fixtures/jma_weather_code.json
python manage.py loaddata taxonomy/fixtures/eggLedger.json

# --- Hospital / AI Agent ---
python manage.py loaddata \
    hospital/fixtures/user.json \
    hospital/fixtures/ward.json \
    hospital/fixtures/city.json \
    hospital/fixtures/election.json \
    hospital/fixtures/userattribute.json \
    hospital/fixtures/voteplace.json

python manage.py loaddata \
    ai_agent/fixtures/entity.json \
    ai_agent/fixtures/guardrail_config.json \
    ai_agent/fixtures/rag_material.json

# --- USA Research ---
python manage.py loaddata usa_research/fixtures/financial_results.json

# 資産クラスの長期推移データの初期取得（1980年以降）
python manage.py monthly_update_historical_assets --start 1980-01-01

# --- Bank ---
python manage.py loaddata bank/fixtures/mufg_summary_master.json
