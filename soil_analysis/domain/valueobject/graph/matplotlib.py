import base64
from io import BytesIO

import matplotlib.pyplot as plt

from .basegraphengine import BaseGraphEngine


class Matplotlib(BaseGraphEngine):
    def plot_graph(self, title, x, y):
        """
        グラフをプロットするための設定
        :param title:
        :param x:
        :param y:
        :return:
        """
        plt.rcParams["font.family"] = ["IPAexGothic"]
        plt.switch_backend("AGG")  # スクリプトを出力させない
        plt.figure(figsize=(5, 2))  # グラフサイズ
        plt.barh(x, y)  # グラフ作成
        plt.xticks(rotation=45)  # X軸値を45度傾けて表示
        plt.title(title)  # グラフタイトル

        buffer = BytesIO()  # バイナリI/O(画像や音声データを取り扱う際に利用)
        plt.tight_layout()
        plt.savefig(buffer, format="png")  # png形式の画像データを取り扱う
        buffer.seek(0)  # ストリーム先頭のoffset byteに変更
        img = buffer.getvalue()  # バッファの全内容を含むbytes
        graph = base64.b64encode(img)  # 画像ファイルをbase64でエンコード
        graph = graph.decode("utf-8")  # デコードして文字列から画像に変換
        buffer.close()

        return graph
