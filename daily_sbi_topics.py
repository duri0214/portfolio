"""
SBI新興国ウィークリーレポートをpdfで取得したあとテキストに変換します
"""
import os
import urllib.request
from datetime import datetime

from bs4 import BeautifulSoup
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage


def download_pdf(out_folder):
    """sbiのtopicを取得"""
    base_url = "https://search.sbisec.co.jp/v2/popwin/info/stock/market_report_fo_em_topic.pdf"
    urllib.request.urlretrieve(base_url, out_folder + "/" + base_url.split("/")[-1])


def convert_pdf_to_text(input_folder):
    """pdfからtextへ変換"""
    input_path = input_folder + '/market_report_fo_em_topic.pdf'
    output_path = input_path.replace(".pdf", ".txt")
    manager = PDFResourceManager()
    with open(output_path, "wb") as txt_output:
        with open(input_path, 'rb') as pdf_input:
            with TextConverter(manager, txt_output, laparams=LAParams()) as conv:
                interpreter = PDFPageInterpreter(manager, conv)
                for page in PDFPage.get_pages(pdf_input):
                    interpreter.process_page(page)


def edit_text_file(input_folder):
    """textを加工"""
    input_path = input_folder + '/market_report_fo_em_topic.txt'
    with open(input_path, encoding='utf-8', mode='r') as txt_input:
        temp = txt_input.read()
    with open(input_path, encoding='utf-8', mode='w') as txt_output:
        pos = temp.find('【韓国】')
        report_date = temp[:pos-1]
        report_date = report_date.replace('\n', '')
        pos = temp.find('【ベトナム】')
        temp = temp[pos:]
        temp = temp.replace('\n', '')
        pos = temp.find('【インドネシア】')
        temp = temp[:pos-1]
        temp = temp.replace('  ▼指数チャート  ', '')
        pos = temp.find('    ')
        temp = temp[:pos-1]
        txt_output.write(report_date + '<br>' + temp)


def get_weekly_topics_us():
    ymd = datetime.today().strftime("%Y%m%d")[-6:]  # e.g. 210215
    print(ymd)
    url = f'https://site3.sbisec.co.jp/ETGate/?OutSide=on&_ControlID=WPLETmgR001Control&_PageID=WPLETmgR001Mdtl20&_DataStoreID=DSWPLETmgR001Control&_ActionID=DefaultAID&getFlg=on&burl=search_market&cat1=market&cat2=report&dir=report&file=market_report_fo_us_wm_{ymd}.html'
    # soup
    soup = BeautifulSoup(urllib.request.urlopen(url).read(), 'lxml')

    for tag_ul in soup.find_all('ul', class_='mgl10 md-l-utl-mt10 fl01'):
        # Symbol, company_name, date
        temp = tag_ul.find_all('li')
        print('a')
        if temp:
            print(temp)
    print('end')

    # # mysql
    # con_str = 'mysql+mysqldb://python:python123@127.0.0.1/pythondb?charset=utf8&use_unicode=1'
    # con = create_engine(con_str, echo=False).connect()
    #
    # # data1 summary data（毎月末のデータが蓄積する）
    # df_summary = pd.DataFrame({
    #     'market_code': mkt,
    # })
    # sql = '''
    #         DELETE FROM vietnam_research_sbi_topics
    #         WHERE market_code = {quote}{market_code}{quote} AND
    #         SUBSTR(pub_date, 1, 10) = {quote}{ymd}{quote}'''
    # sql = sql.format(market_code=mkt, quote='\'', ymd=ymdhms[:10])
    # con.execute(sql)
    # df_summary.to_sql('vietnam_research_industry', con, if_exists='append', index=False)

    return 0  # df_summary.shape[0]

work_folder = os.path.dirname(os.path.abspath(__file__)) + '/mysite/vietnam_research/static/vietnam_research/sbi_topics'
download_pdf(work_folder)
convert_pdf_to_text(work_folder)
edit_text_file(work_folder)
