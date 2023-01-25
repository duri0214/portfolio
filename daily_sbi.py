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
    symbol_codes = []
    url = 'https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_vn_list.html'
    soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')

    for tag_tr in soup.find(class_="accTbl01").tbody.find_all("tr"):
        symbol_codes.append(tag_tr.th.p.string)                  # AAA

    # mysql
    con_str = 'mysql+mysqldb://python:python123@127.0.0.1/pythondb?charset=utf8&use_unicode=1'
    con = create_engine(con_str, echo=False).connect()
    m_symbol = con.execute("SELECT x. * FROM pythondb.vietnam_research_m_symbol x WHERE market_id between 1 and 2")
    m_symbol_records = {row['code']: {'symbol_id': row['id'], 'market_id': row['market_id']} for row in m_symbol}

    sbi = pd.DataFrame({
        'market_id': [m_symbol_records[symbol_code]['market_id'] for symbol_code in symbol_codes],
        'symbol_id': [m_symbol_records[symbol_code]['symbol_id'] for symbol_code in symbol_codes],
    })

    con.execute('DELETE FROM vietnam_research_m_sbi')
    sbi.to_sql('vietnam_research_m_sbi', con, if_exists='append', index=False)

    return len(sbi)


insert_records = scraping()

# log
with open(dirname(abspath(__file__)) + '/result.log', mode='a') as f:
    f.write('\n' + datetime.datetime.now().strftime("%Y/%m/%d %a %H:%M:%S ") + f"daily_sbi.py({len(insert_records)})")

# Output
print('Congrats!')
time.sleep(2)
