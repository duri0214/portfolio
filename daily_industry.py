from os.path import dirname
from os.path import abspath
import re
import urllib.request
import time
import datetime
from sqlalchemy import create_engine
from bs4 import BeautifulSoup
import pandas as pd


def scraping(url: str, mkt: str) -> int:
    """
    viet-kabuから業種情報を取得します

    Args:
        url: 取得先URL
        mkt: 市場コード

    Returns:
        int: 処理したレコード数

    See Also: https://www.viet-kabu.com/stock/hcm.html
    See Also: https://www.viet-kabu.com/stock/hn.html
    """

    symbols = []
    industry_names = []
    market_cap = []
    closing_price = []
    open_price = []
    high_price = []
    low_price = []
    volume = []
    trade_price_of_a_day = []
    per = []
    date = []

    # soup
    soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')

    # date
    # e.g. 'ホーチミン証取株価（2019/08/16 15:00VNT）' => '2019-08-16 15:00:00'
    ymdhms = soup.find('th', class_='table_list_left').text.strip()
    ymdhms = ymdhms.split('（')[1][:16].replace('/', '-') + ':00'

    # data
    for tag_tr in soup.find_all('tr', id=True):
        # Symbol, company_name, date
        temp = tag_tr.find_all('td', class_='table_list_center')
        if temp:
            temp = tag_tr.find_all('td', class_='table_list_center')[0]
            symbol = re.sub("＊", '', temp.text.strip())  # AAA
            print(symbol)
            symbols.append(symbol)
            date.append(ymdhms)                         # 2019-08-16 15:00:00
            # industry1, industry2
            temp = tag_tr.find_all('td', class_='table_list_center')[1]
            industry1 = re.sub(r'\[(.+)\]', '', temp.img.get('title'))
            industry2 = re.search(r'\[(.+)\]', temp.img.get('title')).group(1)
            industry_names.append(industry1 + industry2)
            # closing_price	終値（千ドン）
            temp = tag_tr.find_all('td', class_='table_list_right')[1].text
            closing_price.append(float(temp))
            # open_price	始値（千ドン）
            temp = tag_tr.find_all('td', class_='table_list_right')[2].text
            open_price.append(float(temp))
            # high_price	高値（千ドン）
            temp = tag_tr.find_all('td', class_='table_list_right')[3].text
            high_price.append(float(temp))
            # low_price	安値（千ドン）
            temp = tag_tr.find_all('td', class_='table_list_right')[4].text
            low_price.append(float(temp))
            # volume 出来高（株）
            temp = tag_tr.find_all('td', class_='table_list_right')[7].text
            temp = temp.replace('-', '0').replace(',', '')
            volume.append(float(temp))
            # trade_price_of_a_day 売買代金（千ドン）
            temp = tag_tr.find_all('td', class_='table_list_right')[8].text
            temp = temp.replace('-', '0').replace(',', '')
            trade_price_of_a_day.append(float(temp))
            # market_cap 時価総額（億円）
            temp = tag_tr.find_all('td', class_='table_list_right')[10].text
            temp = temp.replace('-', '0').replace(',', '')
            market_cap.append(float(temp))
            # per 15倍以下が割安
            temp = tag_tr.find_all('td', class_='table_list_right')[11].text
            temp = temp.replace('-', '0')
            per.append(float(temp))

    # mysql
    con_str = 'mysql+mysqldb://python:python123@127.0.0.1/pythondb?charset=utf8&use_unicode=1'
    con = create_engine(con_str, echo=False).connect()

    m_market = con.execute("SELECT id, code FROM pythondb.vietnam_research_m_market")
    market_code_to_id = {row['code']: row['id'] for row in m_market}

    m_symbol = con.execute("SELECT x. * FROM pythondb.vietnam_research_m_symbol x WHERE market_id between 1 and 2")
    symbol_code_to_id = {row['code']: row['id'] for row in m_symbol}
    symbol_ids = [symbol_code_to_id[symbol] for symbol in symbols]

    m_ind_class = con.execute("SELECT concat(industry1, industry2) industry, id FROM pythondb.vietnam_research_m_industry_class")
    industry_name_to_ind_class_id = {row['industry']: row['id'] for row in m_ind_class}

    ind_class_ids = [industry_name_to_ind_class_id[industry_name] for industry_name in industry_names]

    # 日次のデータ
    df_daily_data = pd.DataFrame({
        'recorded_date': date,
        'closing_price': closing_price,
        'open_price': open_price,
        'high_price': high_price,
        'low_price': low_price,
        'volume': volume,
        'trade_price_of_a_day': trade_price_of_a_day,
        'marketcap': market_cap,
        'per': per,
        'created_at': datetime.datetime.today(),
        'market_id': market_code_to_id[mkt],
        'symbol_id': symbol_ids,
        'ind_class_id': ind_class_ids
    })
    sql = f"DELETE FROM vietnam_research_industry WHERE market_id = {market_code_to_id[mkt]} AND SUBSTR(recorded_date, 1, 10) = \'{ymdhms[:10]}\'"
    con.execute(sql)
    df_daily_data.to_sql('vietnam_research_industry', con, if_exists='append', index=False)

    return df_daily_data.shape[0]


def nasdaq():
    import matplotlib.pyplot as plt  # 描画ライブラリ
    # import pandas_datareader.data as web  # データのダウンロードライブラリ
    # tsd = web.DataReader("usmv", "yahoo", "1980/1/1").dropna()  # jpy
    # tsd.loc[:, 'Adj Close'].plot()


CNT = 0

# ホーチミン証券取引所
print('HOSE')
CNT += scraping('https://www.viet-kabu.com/stock/hcm.html', 'HOSE')
# ハノイ証券取引所
print('HNX')
CNT += scraping('https://www.viet-kabu.com/stock/hn.html', 'HNX')

# log
with open(dirname(abspath(__file__)) + '/result.log', mode='a') as f:
    f.write('\n' + datetime.datetime.now().strftime("%Y/%m/%d %a %H:%M:%S ") + f"daily_industry.py({CNT})")

# finish
print(CNT, 'congrats!')
time.sleep(2)
