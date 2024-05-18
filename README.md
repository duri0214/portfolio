# Portfolio

![Static Badge](https://img.shields.io/badge/python-3.11-green)
![Static Badge](https://img.shields.io/badge/django-4.2.8-green)
![Static Badge](https://img.shields.io/badge/mysql-8.0-green)

## TODO

- warehouse
    - カレンダー実装したい gptでやろうとして一回挫折
        - https://chuna.tech/detail/51/
    - 倉庫業務のワークフローをgptに聞く
    - 帳票デザインをgptに聞く
- tabindexの研究

## ライブラリをインストールする

```console
pip install -r requirements.txt

-- ※開発時 現在のライブラリの状態でrequirementsを書き出す
pip freeze > requirements.txt
```

## Migrate

```
python manage.py makemigrations vietnam_research gmarker shopping linebot_engine warehouse taxonomy soil_analysis
python manage.py migrate

python manage.py createsuperuser
```

## fixture

`user` の初期パスワードは `test#1234`

```
python manage.py loaddata .\vietnam_research\fixtures\indClass.json
python manage.py loaddata .\vietnam_research\fixtures\market.json
python manage.py loaddata .\vietnam_research\fixtures\symbol.json
python manage.py loaddata .\vietnam_research\fixtures\sbi.json
python manage.py loaddata .\vietnam_research\fixtures\unit.json
python manage.py loaddata .\vietnam_research\fixtures\vnIndex.json
python manage.py loaddata .\vietnam_research\fixtures\articles.json
python manage.py loaddata .\vietnam_research\fixtures\basicInformation.json
python manage.py loaddata .\vietnam_research\fixtures\financialResultWatch.json
python manage.py loaddata .\vietnam_research\fixtures\industry.json
python manage.py loaddata .\vietnam_research\fixtures\watchlist.json
python manage.py loaddata .\gmarker\fixtures\signageMenuName.json
python manage.py loaddata .\gmarker\fixtures\storeInformation.json
python manage.py loaddata .\shopping\fixtures\store.json
python manage.py loaddata .\shopping\fixtures\staff.json
python manage.py loaddata .\shopping\fixtures\products.json
python manage.py loaddata .\warehouse\fixtures\warehouse.json
python manage.py loaddata .\warehouse\fixtures\staff.json
python manage.py loaddata .\warehouse\fixtures\rentalStatus.json
python manage.py loaddata .\warehouse\fixtures\company.json
python manage.py loaddata .\warehouse\fixtures\billingPerson.json
python manage.py loaddata .\warehouse\fixtures\billingStatus.json
python manage.py loaddata .\taxonomy\fixtures\kingdom.json
python manage.py loaddata .\taxonomy\fixtures\phylum.json
python manage.py loaddata .\taxonomy\fixtures\classification.json
python manage.py loaddata .\taxonomy\fixtures\family.json
python manage.py loaddata .\taxonomy\fixtures\genus.json
python manage.py loaddata .\taxonomy\fixtures\species.json
python manage.py loaddata .\taxonomy\fixtures\naturalMonument.json
python manage.py loaddata .\taxonomy\fixtures\tag.json
python manage.py loaddata .\taxonomy\fixtures\breed.json
python manage.py loaddata .\taxonomy\fixtures\breedTags.json
python manage.py loaddata .\soil_analysis\fixtures\companycategory.json
python manage.py loaddata .\soil_analysis\fixtures\company.json
python manage.py loaddata .\soil_analysis\fixtures\user.json
python manage.py loaddata .\soil_analysis\fixtures\crop.json
python manage.py loaddata .\soil_analysis\fixtures\landblock.json
python manage.py loaddata .\soil_analysis\fixtures\landperiod.json
python manage.py loaddata .\soil_analysis\fixtures\cultivationtype.json
python manage.py loaddata .\soil_analysis\fixtures\land.json
python manage.py loaddata .\soil_analysis\fixtures\samplingmethod.json
python manage.py loaddata .\soil_analysis\fixtures\samplingorder.json
python manage.py loaddata .\soil_analysis\fixtures\landledger.json
python manage.py loaddata .\soil_analysis\fixtures\landreview.json
python manage.py loaddata .\soil_analysis\fixtures\landscorechemical.json
python manage.py loaddata .\soil_analysis\fixtures\device.json
```

## バッチ

```
python manage.py daily_import_from_bloomberg
python manage.py daily_import_from_sbi
python manage.py daily_import_from_vietkabu
python manage.py daily_industry_chart_and_uptrends
python manage.py daily_industry_stacked_bar_chart
```

## インタラクティブシェル

[Mr. Data Converter](https://shancarter.github.io/mr-data-converter/)

```
python manage.py shell

from vietnam_research.models import Industry, IndClass, WatchList
from django.db.models import Sum, F, Case, When, Value
from django.db.models.functions import Concat
  :
```

## サーバを動かす

```
python manage.py runserver
python manage.py import_soil_hardness /path/to/folder
```

## vietnam_research

- ベトナムの株価を分析する

## gmarker

- google map api を使って、マーカーを操作できる

## shopping

- 在庫を登録し、値段・コメントなどの管理ができる

## linebot_engine

- [仕様書](docs/linebot_engine/specification.md)
- あまりできていないが chatbot を作りたかったのかな？

## warehouse

- 倉庫とレンタル業務をイメージしたアプリ
- 何段目の何列目にあるかも登録できる
- 請求書をつくることもできる

## taxonomy

- [仕様書](docs/taxonomy/specification.md)
- 興味のある動物の分類を関係図に表示
- タグ付けをして分析のサポートができる
