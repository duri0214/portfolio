from soil_analysis.models import JmaPrefecture, JmaRegion, JmaAmedas


class JmaRepository:
    @staticmethod
    def get_amedas_code_list(prefecture_id: str, special_add_region_ids: dict) -> dict:
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
