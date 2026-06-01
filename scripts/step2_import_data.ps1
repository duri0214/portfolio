Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path "manage.py")) {
  throw "manage.py not found. Please run this script from the repository root."
}

# --- User Check (ID 1 is required for many fixtures) ---
while ($true) {
    $user_exists = python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(id=1).exists())"
    if ($user_exists.Trim() -eq "True") {
        break
    }
    Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "CRITICAL: Superuser with ID 1 not found." -ForegroundColor Red
    Write-Host "Many fixtures (Vietnam Research, USA Research, etc.) depend on user_id 1." -ForegroundColor Yellow
    Write-Host "Please create a superuser now in another terminal:" -ForegroundColor White
    Write-Host ">> python manage.py createsuperuser" -ForegroundColor Green
    Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
    Read-Host "Press Enter AFTER creating the user to check again, or Ctrl+C to abort."
}

# --- Migrate ---
python manage.py migrate

# --- USA Research (Masters) ---
python manage.py loaddata `
    usa_research\fixtures\market.json `
    usa_research\fixtures\symbol.json `
    usa_research\fixtures\unit.json

# --- Vietnam Research ---
python manage.py loaddata `
    vietnam_research\fixtures\group.json `
    vietnam_research\fixtures\indClass.json `
    vietnam_research\fixtures\market.json `
    vietnam_research\fixtures\symbol.json `
    vietnam_research\fixtures\sbi.json `
    vietnam_research\fixtures\vnIndex.json `
    vietnam_research\fixtures\articles.json `
    vietnam_research\fixtures\basicInformation.json `
    vietnam_research\fixtures\watchlist.json

# Batches for Vietnam Research
python manage.py daily_import_market_data
python manage.py daily_import_from_sbi
python manage.py daily_import_usa_from_sbi
python manage.py daily_import_from_vietkabu

# Data generation and charts
# Note: --clear is for initial data.
python manage.py generate_industry_dummy_data --clear
python manage.py daily_industry_chart_and_uptrend
python manage.py daily_industry_stacked_bar_chart

# FAO Food Balance / Vietnam Statistics
python manage.py monthly_fao_food_balance_chart
# Using dummy data for statistics due to server certificate issues
python manage.py generate_vietnam_statistics_dummy_data --clear

# --- GMarker ---
python manage.py loaddata `
    gmarker\fixtures\place.json `
    gmarker\fixtures\nearbyPlace.json

# --- Shopping ---
python manage.py loaddata `
    shopping\fixtures\user.json `
    shopping\fixtures\store.json `
    shopping\fixtures\userattribute.json `
    shopping\fixtures\product.json

# --- Rental Shop (Warehouse) ---
python manage.py loaddata `
    rental_shop\fixtures\warehouse.json `
    rental_shop\fixtures\user.json `
    rental_shop\fixtures\userattribute.json `
    rental_shop\fixtures\rentalStatus.json `
    rental_shop\fixtures\company.json `
    rental_shop\fixtures\billingPerson.json `
    rental_shop\fixtures\billingStatus.json `
    rental_shop\fixtures\warehousestaff.json `
    rental_shop\fixtures\item.json

# --- Soil Analysis ---
python manage.py loaddata `
    soil_analysis\fixtures\user.json `
    soil_analysis\fixtures\userattribute.json `
    soil_analysis\fixtures\companycategory.json `
    soil_analysis\fixtures\company.json `
    soil_analysis\fixtures\crop.json `
    soil_analysis\fixtures\land_block.json `
    soil_analysis\fixtures\land_period.json `
    soil_analysis\fixtures\cultivationtype.json

# Batches for Soil Analysis master data
python manage.py weather_load_const_master

python manage.py loaddata soil_analysis\fixtures\jma_weather_code.json
python manage.py loaddata soil_analysis\fixtures\land.json
python manage.py loaddata soil_analysis\fixtures\rokunohe_land_registry.json

# Weather data fetch
python manage.py weather_fetch_forecast
python manage.py weather_fetch_warning

python manage.py loaddata soil_analysis\fixtures\samplingmethod.json
python manage.py loaddata soil_analysis\fixtures\samplingorder.json
python manage.py loaddata soil_analysis\fixtures\land_ledger.json
python manage.py loaddata soil_analysis\fixtures\land_review.json
python manage.py loaddata soil_analysis\fixtures\device.json

# --- Taxonomy ---
python manage.py loaddata `
    taxonomy\fixtures\kingdom.json `
    taxonomy\fixtures\phylum.json `
    taxonomy\fixtures\classification.json `
    taxonomy\fixtures\family.json `
    taxonomy\fixtures\genus.json `
    taxonomy\fixtures\species.json `
    taxonomy\fixtures\naturalMonument.json `
    taxonomy\fixtures\tag.json `
    taxonomy\fixtures\breed.json `
    taxonomy\fixtures\breedTags.json `
    taxonomy\fixtures\feedGroup.json `
    taxonomy\fixtures\henGroup.json

# Batches for Taxonomy master data
python manage.py loaddata taxonomy\fixtures\jma_weather_code.json
python manage.py loaddata taxonomy\fixtures\eggLedger.json

# --- Hospital / AI Agent ---
python manage.py loaddata `
    hospital\fixtures\user.json `
    hospital\fixtures\ward.json `
    hospital\fixtures\city.json `
    hospital\fixtures\election.json `
    hospital\fixtures\userattribute.json `
    hospital\fixtures\voteplace.json

python manage.py loaddata `
    ai_agent\fixtures\entity.json `
    ai_agent\fixtures\guardrail_config.json `
    ai_agent\fixtures\rag_material.json

# --- USA Research ---
python manage.py loaddata usa_research\fixtures\financial_results.json

# Historical asset data update (from 1950)
python manage.py monthly_update_historical_assets --start 1950-01-01

# --- Bank ---
python manage.py loaddata bank\fixtures\mufg_summary_master.json
