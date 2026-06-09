import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "六戸町の会議録PDFを一括ダウンロードします"

    def handle(self, *args, **options):
        # 現行ページとバックナンバーページのURL
        target_urls = [
            "https://www.town.rokunohe.aomori.jp/docs/2023051900005",
        ]

        # 保存先ディレクトリ
        save_dir = "rokunohe_pdf_backnumbers"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            self.stdout.write(f"ディレクトリを作成しました: {save_dir}")

        downloaded_filenames = set()

        for target_url in target_urls:
            self.stdout.write(f"処理中: {target_url}")
            try:
                response = requests.get(target_url)
                response.raise_for_status()
                # エンコーディングを自動検出（Shift_JISなどの場合があるため）
                response.encoding = response.apparent_encoding

                soup = BeautifulSoup(response.text, "html.parser")

                # PDFへのリンクを探す
                # 六戸町のサイトでは [PDF：...KB] というテキストが含まれるリンクが多い
                links = soup.find_all("a")

                pdf_count = 0
                for link in links:
                    href = link.get("href")
                    if not href:
                        continue

                    # URLが .pdf で終わるか、リンクテキストに [PDF という文字列が含まれる場合
                    text = link.get_text()
                    if href.lower().endswith(".pdf") or "[PDF" in text:
                        pdf_url = urljoin(target_url, href)

                        # 404対策: リンクが相対パスで /docs/2023051900005 からの相対ではなく
                        # /docs/ からの相対である可能性があるため、調整を試みる
                        # web_searchの結果では file_contents/071209.pdf となっていた
                        # 実際のURLが https://www.town.rokunohe.aomori.jp/docs/file_contents/071209.pdf なら 404
                        # おそらく https://www.town.rokunohe.aomori.jp/file_contents/071209.pdf か
                        # https://www.town.rokunohe.aomori.jp/docs/2023051900005/file_contents/071209.pdf
                        # web_searchの1番目の結果のURLは https://www.town.rokunohe.aomori.jp/docs/2023051900005
                        # そこでのリンクが file_contents/071209.pdf なら、
                        # 通常は https://www.town.rokunohe.aomori.jp/docs/file_contents/071209.pdf になる
                        # しかし、もし /docs/2023051900005/ (末尾スラッシュあり) なら
                        # https://www.town.rokunohe.aomori.jp/docs/2023051900005/file_contents/071209.pdf になる

                        if not target_url.endswith("/"):
                            # スラッシュがない場合、urljoinは最後のコンポーネントをファイルとみなして置き換える
                            # そのため https://www.town.rokunohe.aomori.jp/docs/file_contents/071209.pdf になっていた
                            # 期待されるのは https://www.town.rokunohe.aomori.jp/docs/2023051900005/file_contents/071209.pdf
                            # またはドメイン直下
                            pdf_url = urljoin(target_url + "/", href)

                        # ファイル名を取得
                        filename = os.path.basename(href)
                        if not filename.lower().endswith(".pdf"):
                            filename += ".pdf"

                        if filename in downloaded_filenames:
                            self.stdout.write(f"スキップ (重複): {filename}")
                            continue

                        # 保存パス
                        save_path = os.path.join(save_dir, filename)

                        # ダウンロード
                        self.stdout.write(f"ダウンロード中: {pdf_url}")
                        pdf_response = requests.get(pdf_url)
                        pdf_response.raise_for_status()

                        with open(save_path, "wb") as f:
                            f.write(pdf_response.content)

                        downloaded_filenames.add(filename)
                        pdf_count += 1
                        self.stdout.write(self.style.SUCCESS(f"保存完了: {save_path}"))

                self.stdout.write(f"合計 {pdf_count} 件のPDFを処理しました。")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"エラーが発生しました ({target_url}): {e}")
                )
