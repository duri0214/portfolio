from soil_analysis.models import JmaPrefecture, JmaRegion, JmaAmedas


class JmaRepository:
    @staticmethod
    def get_amedas_code_list(prefecture_id: str, special_add_region_ids: dict) -> dict:
        """
        指定された都道府県およびその地域に関連したAMEDASコードを返す。

        辞書のキーは地域コード、値はその地域に関連したAMEDASコードのリストを持つ。
        都道府県に特別地域IDが設定されている場合、それらも結果の辞書に含まれる。

        このメソッドは、Django のバッチ処理内（例: `weather_fetch_forecast` バッチ）で
        天気データ収集用の地域ごとのAMEDASコードを取得するために使用される。

        Args:
            prefecture_id (str): 都道府県のID。
            special_add_region_ids (dict): 特別な地域IDとそれに対応するAMEDAS地域のマッピング。

        Returns:
            dict: 地域コードとAMEDASコードリストのマッピング。

        Notes:
            - この関数は主に Django の管理バッチ処理で使用されています。
            - 再利用可能なロジックとして整理されているため、他のスクリプトでも利用可能です。
        """
        amedas_code_in_region = {}
        jma_regions = JmaRegion.objects.filter(
            jma_prefecture=JmaPrefecture.objects.get(code=prefecture_id)
        ).prefetch_related("jmaamedas_set")

        for region in jma_regions:
            amedas_code_in_region[region.code] = [
                amedas.code for amedas in region.jmaamedas_set.all()
            ]

        if prefecture_id in special_add_region_ids:
            region = JmaRegion.objects.get(code=special_add_region_ids[prefecture_id])
            special_add_region_code = special_add_region_ids[prefecture_id]
            amedas_code_in_region[special_add_region_code] = list(
                JmaAmedas.objects.filter(jma_region=region).values_list(
                    "code", flat=True
                )
            )

        return amedas_code_in_region
