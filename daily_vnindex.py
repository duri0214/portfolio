"""vn-indexを取り込みます
https://www.bloomberg.co.jp/quote/VNINDEX:IND
"""
from os.path import dirname, abspath
import urllib.request
import time
import datetime
from sqlalchemy import create_engine
from bs4 import BeautifulSoup
import pandas as pd


def scraping():
    """
    url先の <div id="last_last"> の <tr> を取得する。
    """
    url = 'https://www.bloomberg.co.jp/quote/VNINDEX:IND'
    soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')
    ymd = soup.find(class_="price-datetime").text.split()[-1]
    price = soup.find(class_="price").text.replace(',', '')
    vn_index = pd.DataFrame({
        'Y': ymd.split('/')[0],
        'M': ymd.split('/')[1],
        'closing_price': price
    }, index=[0])

    # mysql
    today = datetime.date.today()
    con_str = 'mysql+mysqldb://python:python123@127.0.0.1/pythondb?charset=utf8&use_unicode=1'
    con = create_engine(con_str, echo=False).connect()
    year = today.year
    month = today.month
    sql = f'DELETE FROM vietnam_research_vnindex WHERE Y = {year} AND M = {month}'
    con.execute(sql)
    vn_index.to_sql('vietnam_research_vnindex', con, if_exists='append', index=False)


scraping()

# log
with open(dirname(abspath(__file__)) + '/result.log', mode='a') as f:
    f.write('\n' + datetime.datetime.now().strftime("%Y/%m/%d %a %H:%M:%S ") + 'daily_vnindex.py')

# finish
print('Congrats!')
time.sleep(2)
