# Portfolio

![Static Badge](https://img.shields.io/badge/python-3.11-green)
![Static Badge](https://img.shields.io/badge/django-4.2.8-green)
![Static Badge](https://img.shields.io/badge/mysql-8.0-green)

## ライブラリをインストールする

```console
pip install -r requirements.txt

-- ※開発時 現在のライブラリの状態でrequirementsを書き出す
pip freeze > requirements.txt
```

## すべてのテーブルをカラにする

```
python manage.py flush --noinput
```

## Migrate

- サーバで実行するときは `python3` にしてバッククォートを `/` に置換する

```
python manage.py makemigrations vietnam_research gmarker shopping linebot_engine warehouse taxonomy soil_analysis securities
python manage.py migrate

python manage.py createsuperuser
```

## fixture

- `user` の初期パスワードは `test#1234`
- サーバで実行するときは `python3` にしてバッククォートを `/` に置換する
- createsuperuser をやったあとじゃないと失敗するfixtureがあるよ
- バッチ `daily_industry_chart_and_uptrend` を動かすときは `industry` の seeder は14日ぶん用意しましょう
    - seederの日付はだんだん古くなっていくのでメンテしてね

```text
SELECT x.recorded_date
FROM portfolio_db.vietnam_research_industry x
GROUP BY x.recorded_date;
UPDATE portfolio_db.vietnam_research_industry
SET recorded_date = '2024-05-02'
WHERE recorded_date = '2023-01-17';
```

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

## よくつかうメンテナンスコマンド

```commandline
cd /var/www/html/portfolio
source /var/www/html/venv/bin/activate
systemctl restart apache2
chown -R ubuntu:ubuntu /var/www/html
python manage.py collectstatic
```

## vietnam_research

`daily_industry_chart_and_uptrend` は 各期間（14日、7日、3日）を遡り、 すべての期間の株価が上昇傾向（斜度が正）であれば passed
がインクリメントされる。つまり時系列データがないと画像は保存されない

- ベトナムの株価を分析する
    - `python manage.py daily_import_from_bloomberg` のバッチをまわす
    - `python manage.py daily_import_from_sbi` のバッチをまわす
    - `python manage.py daily_import_from_vietkabu` のバッチをまわす
    - `python manage.py daily_industry_chart_and_uptrend` のバッチをまわす
    - `python manage.py daily_industry_stacked_bar_chart` のバッチをまわす
- FAOから水産物供給量の推移グラフ
    - `python manage.py fao_food_balance_chart` のバッチをまわす

## gmarker

- google map api を使って、マーカーを操作できる

## shopping

- 在庫を登録し、値段・コメントなどの管理ができる

## linebot_engine

https://qiita.com/YoshitakaOkada/items/f51f52a8041439a1dbc9#line

- [仕様書](docs/linebot_engine/specification.md)
- 当時ヘルスチェックを作りたかったらしい
    - LINE: （朝8時ごろに）元気？
    - User: 元気です
    - LINE: 朝ご飯食べた？
    - User: 食べた

Userが「食べた」と答えた回数を集計して、最近「食べた」と答えなかったらアラート、みたいな

## warehouse

- 倉庫とレンタル業務をイメージしたアプリ
- 何段目の何列目にあるかも登録できる
- 請求書をつくることもできる

## taxonomy

- [仕様書](docs/taxonomy/specification.md)
- 興味のある動物の分類を関係図に表示
- タグ付けをして分析のサポートができる
