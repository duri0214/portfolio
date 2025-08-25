import json

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from welfare_services.domain.valueobject.facility import WelfareFacilityVO
from welfare_services.models import Facility


class Command(BaseCommand):
    help = "東京都オープンデータAPIから福祉事務所データを取得します"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        self.stdout.write("福祉事務所データ取得を開始します...")

        # APIのURL
        api_url = "https://service.api.metro.tokyo.lg.jp/api/t000010d1800000028-392e7b533d4917e6c8a7e7a4a05e1420-0/json"

        try:
            # APIからデータを取得 - POSTリクエストで空のJSONボディを送信
            headers = {"Content-Type": "application/json"}
            response = requests.post(api_url, json={}, headers=headers)
            response.raise_for_status()

            # JSONデータをパース
            data = response.json()

            # APIレスポンスの構造を確認
            if not isinstance(data, dict):
                raise ValueError(f"APIレスポンスが予期しない型です: {type(data)}")

            # hitsデータを確認
            if "hits" not in data:
                error_msg = "APIレスポンスにhitsキーがありません"
                self.stdout.write(self.style.ERROR(error_msg))
                raise ValueError(error_msg)

            hits = data["hits"]
            self.stdout.write(f"福祉施設データ件数: {len(hits)}件")
            if len(hits) > 0:
                first_item = hits[0]
                self.stdout.write(f"データ項目の例: {list(first_item.keys())}")

            # APIからデータが取得できたかを確認
            if not data:
                self.stdout.write(
                    self.style.WARNING("APIからデータが取得できませんでした。")
                )

            # トランザクション内のすべての操作が成功すれば、その変更が確定（コミット）されます
            with transaction.atomic():
                self._save_facilities(data)

            self.stdout.write(self.style.SUCCESS(f"処理が完了しました"))

        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"API呼び出しエラー: {e}"))
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f"JSONパースエラー: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"予期せぬエラー: {e}"))

    def _save_facilities(self, data):
        """APIから取得したデータをDBに保存"""

        # 東京都APIの構造に合わせて処理（hitsキーにデータ配列がある）
        if "hits" not in data:
            error_msg = "データにhitsキーがありません"
            self.stdout.write(self.style.ERROR(error_msg))
            raise ValueError(error_msg)

        facilities_data = data["hits"]

        # 処理するデータ数を確認
        count = 0
        total = len(facilities_data)

        for item in facilities_data:
            try:
                vo = WelfareFacilityVO.from_api_response(item)

                # データの検証
                if not vo.name:
                    self.stdout.write(self.style.WARNING(f"施設名が不明です: {item}"))
                    continue

                # Facilityモデルにデータを保存
                facility, created = Facility.objects.update_or_create(
                    name=vo.name,
                    defaults={
                        "postal_code": vo.postal_code,
                        "address": vo.address,
                        "phone": vo.phone,
                        "fax": vo.fax,
                        "latitude": vo.latitude,
                        "longitude": vo.longitude,
                        "coordinate_system": vo.coordinate_system,
                    },
                )

                # 作成または更新の状態を1行のログに出力
                action = "作成" if created else "更新"
                self.stdout.write(f"{vo.name}: {action}されました")

                count += 1
                if count % 10 == 0 or count == total:
                    self.stdout.write(f"{count}/{total} 件処理中...")

            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"施設データ保存エラー: {e} - データ: {item}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"合計 {count} 件の施設データを処理しました")
        )
