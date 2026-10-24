Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

if (-not (Test-Path "manage.py")) {
  throw "manage.py not found. Please run this script from the repository root."
}

if (Test-Path ".\.venv\Scripts\python.exe") {
    $pythonExe = (Resolve-Path ".\.venv\Scripts\python.exe").Path
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = "python"
} else {
    throw "Python not found. Create .venv or add python to PATH."
}

function Invoke-Manage {
    & $pythonExe manage.py @args
    if ($LASTEXITCODE -ne 0) {
        throw "manage.py $($args -join ' ') failed with exit code $LASTEXITCODE."
    }
}

# --- User Check (ID 1 is required for some fixtures) ---
while ($true) {
    $userExists = Invoke-Manage shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(id=1).exists())"
    if ($userExists -match "True") {
        break
    }
    Write-Host "----------------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "ID 1 のユーザーが必要です。別のターミナルで次を実行してください。" -ForegroundColor Yellow
    Write-Host ">> $pythonExe manage.py createsuperuser" -ForegroundColor Green
    Write-Host "ユーザー作成後、この画面でEnterを押すとSeederを再開します。" -ForegroundColor White
    Read-Host "Enterで再確認、Ctrl+Cで中止"
}

# --- Migrate ---
Invoke-Manage migrate

# --- USA Research (Masters) ---
Invoke-Manage loaddata `
    usa_research\fixtures\market.json `
    usa_research\fixtures\symbol.json `
    usa_research\fixtures\unit.json

# --- Vietnam Research ---
Invoke-Manage loaddata `
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
Invoke-Manage daily_import_market_data
Invoke-Manage daily_import_from_sbi
Invoke-Manage daily_import_usa_from_sbi
Invoke-Manage daily_import_from_vietkabu

# Data generation and charts
# Note: --clear is for initial data.
Invoke-Manage generate_industry_dummy_data --clear
Invoke-Manage daily_industry_chart_and_uptrend
Invoke-Manage daily_industry_stacked_bar_chart

# FAO Food Balance / Vietnam Statistics
Invoke-Manage monthly_fao_food_balance_chart
# Using dummy data for statistics due to server certificate issues
Invoke-Manage generate_vietnam_statistics_dummy_data --clear

# --- GMarker ---
Invoke-Manage loaddata `
    gmarker\fixtures\place.json `
    gmarker\fixtures\nearbyPlace.json

# --- Shopping ---
Invoke-Manage loaddata `
    shopping\fixtures\user.json `
    shopping\fixtures\store.json `
    shopping\fixtures\userattribute.json `
    shopping\fixtures\product.json

# --- Rental Shop (Warehouse) ---
Invoke-Manage loaddata `
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
Invoke-Manage loaddata `
    soil_analysis\fixtures\user.json `
    soil_analysis\fixtures\userattribute.json `
    soil_analysis\fixtures\companycategory.json `
    soil_analysis\fixtures\company.json `
    soil_analysis\fixtures\land_block.json `
    soil_analysis\fixtures\land_period.json `
    soil_analysis\fixtures\cultivationtype.json

# Batches for Soil Analysis master data
Invoke-Manage weather_load_const_master

Invoke-Manage loaddata soil_analysis\fixtures\jma_weather_code.json
Invoke-Manage loaddata soil_analysis\fixtures\rokunohe_land_registry.json

Invoke-Manage loaddata soil_analysis\fixtures\samplingmethod.json
Invoke-Manage generate_prefecture_representative_fixtures

# Weather data fetch
try {
    Invoke-Manage weather_fetch_forecast
} catch {
    Write-Warning "weather_fetch_forecast failed. JMA API may be temporarily unavailable; continuing import."
}
try {
    Invoke-Manage weather_fetch_warning
} catch {
    Write-Warning "weather_fetch_warning failed. JMA API may be temporarily unavailable; continuing import."
}

Invoke-Manage loaddata soil_analysis\fixtures\samplingorder.json
Invoke-Manage loaddata soil_analysis\fixtures\device.json

# --- Taxonomy ---
Invoke-Manage seed_taxonomy_data

# --- Hospital ---
Invoke-Manage loaddata `
    hospital\fixtures\user.json `
    hospital\fixtures\ward.json `
    hospital\fixtures\city.json `
    hospital\fixtures\election.json `
    hospital\fixtures\userattribute.json `
    hospital\fixtures\voteplace.json

# --- USA Research ---
Invoke-Manage loaddata usa_research\fixtures\financial_results.json

# Historical asset data update (from 1980)
Invoke-Manage monthly_update_historical_assets --start 1980-01-01

# --- Bank ---
Invoke-Manage loaddata bank\fixtures\mufg_summary_master.json
