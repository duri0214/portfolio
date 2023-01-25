"""
傾斜を出して、uptrendを算出
"""
from glob import glob
import os
from pathlib import Path
import time
import datetime
from sqlalchemy import create_engine
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
from mysite.mysite.settings import BASE_DIR

# mysql
CON_STR = 'mysql+mysqldb://python:python123@127.0.0.1/pythondb?charset=utf8&use_unicode=1'
CON = create_engine(CON_STR, echo=False).connect()

# uptrend by industry
print('\n' + 'uptrend')
OUTFOLDER = BASE_DIR.resolve().joinpath('vietnam_research/static/vietnam_research/chart')
for filename in glob(Path(OUTFOLDER).joinpath('*.png').__str__()):
    os.remove(filename)

CON.execute('DELETE FROM vietnam_research_dailyuptrends')
AGG = pd.read_sql_query(
    '''
    SELECT
          c.industry1
        , c.industry2
        , vrmm.code market_code
        , vrms.code symbol
        , i.recorded_date 
        , i.closing_price 
    FROM (vietnam_research_industry i 
        INNER JOIN vietnam_research_m_industry_class c ON i.ind_class_id = c.id)
        inner join vietnam_research_m_symbol vrms ON i.symbol_id = vrms.id 
        inner join vietnam_research_m_market vrmm on vrms.market_id = vrmm.id 
        INNER JOIN vietnam_research_m_sbi s ON vrmm.id = s.market_id AND vrms.id = s.symbol_id
    ORDER BY c.industry1, c.industry2, i.symbol_id, i.recorded_date;
    ''', CON)
print(AGG)
IND_NAMES = []
MARKET_CODES = []
SYMBOLS = []
PRICE_OLDEST = []
PRICE_LATEST = []
PRICE_DELTAS = []
for symbol_code, values in AGG.groupby('symbol'):
    days = [14, 7, 3]
    # plot: closing_price
    plt.clf()
    plt.plot(range(len(values)), values['closing_price'], "ro")
    plt.plot(range(len(values)), values['closing_price'].rolling(20).mean(), "r-", label="20SMA")
    plt.plot(range(len(values)), values['closing_price'].rolling(40).mean(), "g-", label="40SMA")
    plt.legend(loc="upper left")
    plt.ylabel('closing_price')
    plt.grid()
    slope_inner = []
    price_inner = []
    score = 0
    iteration_count = 0
    for i, v in enumerate(days):
        if len(values) > days[i]:
            # count
            iteration_count += 1
            # fetch filtered days e.g. 3 days, 7 days, 14 days ...
            values_inner = values[-days[i]:]
            x_scale = range(len(values_inner))
            A = np.array([x_scale, np.ones(len(x_scale))]).T
            # get slope
            slope, intercept = np.linalg.lstsq(A, values_inner['closing_price'], rcond=-1)[0]
            slope_inner.append(slope)
            # scoring
            if slope > 0:
                score += 1
            # plot: overwrite fitted line
            x_offset = len(values) - days[i]
            x_scale_shifted = range(x_offset, days[i] + x_offset)
            plt.plot(x_scale_shifted, (slope * x_scale + intercept), "g--")
            # save png: w640, h480
            out_path = Path(OUTFOLDER).joinpath('{0}.png').__str__().format(symbol_code)
            print(os.path.exists(out_path), out_path)
            plt.savefig(out_path)
            # resize png: w250, h200
            Image.open(out_path).resize((250, 200), Image.LANCZOS).save(out_path)
    if score == iteration_count:
        # stack param（Notes: ひとつのsymbol_codeがすべての期間のデータを持っているので、head(1)で処理する）
        IND_NAMES.append(values['industry1'].head(1).iloc[0] + values['industry2'].head(1).iloc[0])
        MARKET_CODES.append(values['market_code'].head(1).iloc[0])
        SYMBOLS.append(symbol_code)
        price_inner.append(values.tail(max(days))['closing_price'].head(1).iloc[0])
        price_inner.append(values.tail(max(days))['closing_price'].tail(1).iloc[0])
        price_inner.append(round(price_inner[1] - price_inner[0], 2))
        PRICE_OLDEST.append(price_inner[0])
        PRICE_LATEST.append(price_inner[1])
        PRICE_DELTAS.append(price_inner[2])
    print(symbol_code, slope_inner, score, price_inner)

m_market = CON.execute("SELECT id, code FROM pythondb.vietnam_research_m_market")
market_code_to_id = {row['code']: row['id'] for row in m_market}

m_symbol = CON.execute("SELECT x. * FROM pythondb.vietnam_research_m_symbol x WHERE market_id between 1 and 2")
symbol_code_to_id = {row['code']: {'id': row['id'], 'market_id': row['market_id']} for row in m_symbol}
symbol_ids = [symbol_code_to_id[symbol] for symbol in SYMBOLS]  # TODO: スキーマ変更の影響で見にくいけど idsだけど SYMBOLS ですりきりした m_symbol

m_ind_class = CON.execute("SELECT concat(industry1, industry2) industry, id FROM pythondb.vietnam_research_m_industry_class")
industry_name_to_ind_class_id = {row['industry']: row['id'] for row in m_ind_class}

ind_class_ids = [industry_name_to_ind_class_id[industry_name] for industry_name in list(IND_NAMES)]
extract = pd.DataFrame({
    'stocks_price_oldest': PRICE_OLDEST,
    'stocks_price_latest': PRICE_LATEST,
    'stocks_price_delta': PRICE_DELTAS,
    'symbol_id': [x['id'] for x in symbol_ids],
    'market_id': [x['market_id'] for x in symbol_ids],
    'ind_class_id': ind_class_ids
})
extract = extract.sort_values(['ind_class_id', 'stocks_price_delta'], ascending=[True, False])
extract.to_sql('vietnam_research_dailyuptrends', CON, if_exists='append', index=None)

# log
with open(os.path.dirname(os.path.abspath(__file__)) + '/result.log', mode='a') as f:
    f.write('\n' + datetime.datetime.now().strftime("%Y/%m/%d %a %H:%M:%S ") + f"daily_chart.py({len(extract)})")

# Output
print('Congrats!')
time.sleep(2)
