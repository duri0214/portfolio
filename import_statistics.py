"""ベトナム統計を取り込みます
https://www.gso.gov.vn/Default_en.aspx?tabid=766
"""
import datetime
from sqlalchemy import create_engine
import pandas as pd

# E08.01.csv: 商品およびサービス(小売)のカテゴリー別売上高（単位: 10億ドン）
# 小売(Retail)・宿泊飲食サービス(Inn)・サービスと観光(Tourism)
COLS = ['Year', 'Total', 'Retail sale', 'Accommodation, food and beverage service']
COLS.extend(['Service and tourism'])
STAT = pd.read_csv('import/csv/E08.01.csv', usecols=COLS, sep=';', header=1)
COLS_NEW = ['Year', 'Total_dong_1B', 'Retail_dong_1B', 'Inn_dong_1B', 'Tourism_dong_1B']
STAT = STAT.rename(columns=dict(zip(COLS, COLS_NEW)))
STAT['Year'] = STAT['Year'].str[-4:].astype(int)
STAT['Retail_per'] = (STAT['Retail_dong_1B'] / STAT['Total_dong_1B']).round(2)
STAT['Inn_per'] = (STAT['Inn_dong_1B'] / STAT['Total_dong_1B']).round(2)
STAT['Tourism_dong_1B'] = STAT['Tourism_dong_1B'].replace('..', 0)
STAT['Tourism_per'] = (STAT['Tourism_dong_1B'].astype(float) / STAT['Total_dong_1B']).round(2)
COLS_OUT = ['Year', 'Total_dong_1B', 'Retail_dong_1B', 'Retail_per', 'Inn_dong_1B', 'Inn_per']
COLS_OUT.extend(['Tourism_dong_1B', 'Tourism_per'])
STAT = STAT[COLS_OUT]
print(STAT)

# E08.06.csv: 商品の輸出入（Mill.USD）
# (*) 輸出 - 輸入
# (**) 2015年以降は航空会社が外国の空港で購入した燃料の価値が含まれる
COLS = ['Year', 'Total', 'Exports', 'Imports (**)', 'Balance(*)']
STAT = pd.read_csv('import/csv/E08.06.csv', usecols=COLS, sep=';', header=1)
COLS_NEW = ['Year', 'Total_usd_1M', 'Exports_usd_1M', 'Imports_usd_1M', 'Balance_usd_1M']
STAT = STAT.rename(columns=dict(zip(COLS, COLS_NEW)))
STAT['Year'] = STAT['Year'].str[-4:].astype(int)
STAT = STAT[COLS_NEW]
print(STAT)

# E08.11.csv: 国グループ、国および地域による商品の輸出（Mill. USD）
COLS = ['Country and territory', 'Year']
COLS.extend(['Exports of goods by country group, country and territory'])
STAT = pd.read_csv('import/csv/E08.11.csv', usecols=COLS, sep=';', header=1)
COLS_NEW = ['Country', 'Year', 'Exports_usd_1M']
STAT = STAT.rename(columns=dict(zip(COLS, COLS_NEW)))
STAT['Year'] = STAT['Year'].str[-4:].astype(int)
STAT['Exports_usd_1M'] = STAT['Exports_usd_1M'].replace('..', 0).astype(float)
STAT = STAT[COLS_NEW]
# (db登録はこのタイミング)
STAT = STAT.pivot('Country', 'Year', 'Exports_usd_1M')
print(STAT)

# E08.12.csv: 輸出用の主な商品
COLS = ['Main goods', 'Year', 'Some main goods for exportation']
STAT = pd.read_csv('import/csv/E08.12.csv', usecols=COLS, sep=';', header=1)
COLS_NEW = ['goods', 'Year', 'amount']
STAT = STAT.rename(columns=dict(zip(COLS, COLS_NEW)))
STAT['Year'] = STAT['Year'].str[-4:].astype(int)
STAT['amount'] = STAT['amount'].replace('..', 0).astype(float)
STAT = STAT[COLS_NEW]
# (db登録はこのタイミング)
STAT = STAT.pivot('goods', 'Year', 'amount')
print(STAT)

# mysql
# CON_STR = 'mysql+mysqldb://root:mysql0214@localhost/pythondb?charset=utf8&use_unicode=1'
# CON = create_engine(CON_STR, echo=False).connect()
# CON.execute('DELETE FROM vietnam_research_vnindex')
# STAT.to_sql('vietnam_research_vnindex', CON, if_exists='append', index=None)

# # log
# with open('result.log', mode='a') as f:
#     f.write('\n' + datetime.datetime.now().strftime("%Y/%m/%d %a %H:%M:%S ") + 'stat.py')

# # finish
# print('Congrats!')
