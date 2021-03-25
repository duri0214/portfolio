"""
SBI証券ベトナム株式取扱銘柄一覧を取得します
"""
from os.path import dirname
from os.path import abspath
import urllib.request
import time
import datetime
from sqlalchemy import create_engine
from bs4 import BeautifulSoup
import pandas as pd

def scraping():
    """
    url先の <div class="accTbl01"> の <tr> を取得する。
    """
    market_code = []
    symbol_code = []
    url = 'https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_vn_list.html'
    soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')

    for tag_tr in soup.find(class_="accTbl01").tbody.find_all("tr"):
        symbol_code.append(tag_tr.th.p.string)                  # AAA
        market_code.append(tag_tr.find_all('td')[2].p.string)   # HOSE

    sbi = pd.DataFrame({
        'market_code': market_code,
        'symbol': symbol_code,
    })

    # mysql
    con_str = 'mysql+mysqldb://python:python123@127.0.0.1/pythondb?charset=utf8&use_unicode=1'
    con = create_engine(con_str, echo=False).connect()
    con.execute('DELETE FROM vietnam_research_sbi')
    sbi.to_sql('vietnam_research_sbi', con, if_exists='append', index=None)

scraping()


# log
with open(dirname(abspath(__file__)) + '/result.log', mode='a') as f:
    f.write('\n' + datetime.datetime.now().strftime("%Y/%m/%d %a %H:%M:%S ") + 'sbi.py')

# Output
print('Congrats!')
time.sleep(2)
