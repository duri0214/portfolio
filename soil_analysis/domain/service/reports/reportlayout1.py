from django.db.models import Avg

from soil_analysis.domain.service.reports.basereportlayout import BaseReportLayout
from soil_analysis.domain.valueobject.graph.matplotlib import Matplotlib
from soil_analysis.models import LandLedger, LandScoreChemical


class ReportLayout1(BaseReportLayout):
    def __init__(self, landledger: LandLedger):
        self._landledger = landledger
        self._landscores = LandScoreChemical.objects.filter(landledger=landledger)
        self._landscores_agg = self._landscores_aggregate()

    def _landscores_aggregate(self):
        """
        landscoresの平均
        """
        return self._landscores.aggregate(
            Avg('ec'), Avg('nh4n'), Avg('no3n'), Avg('total_nitrogen'), Avg('nh4_per_nitrogen'),
            Avg('ph'), Avg('cao'), Avg('mgo'), Avg('k2o'), Avg('base_saturation'), Avg('cao_per_mgo'),
            Avg('mgo_per_k2o'), Avg('phosphorus_absorption'), Avg('p2o5'), Avg('cec'), Avg('humus'),
            Avg('bulk_density'),
        )

    def publish(self, *args):
        g = Matplotlib()

        x = ['EC(mS/cm)', 'NH4-N(mg/100g)', 'NO3-N(mg/100g)', '無機態窒素', 'NH4/無機態窒素', ' ', '  ']
        y = [
            self._landscores_agg['ec__avg'],
            self._landscores_agg['nh4n__avg'],
            self._landscores_agg['no3n__avg'],
            self._landscores_agg['total_nitrogen__avg'],
            self._landscores_agg['nh4_per_nitrogen__avg'],
            0,
            0
        ]
        chart1 = g.plot_graph("窒素関連（1圃場の全エリア平均）", x, y)

        x = ['ph', 'CaO(mg/100g)', 'MgO(mg/100g)', 'K2O(mg/100g)', '塩基飽和度(%)', 'CaO/MgO', 'MgO/K2O']
        y = [
            self._landscores_agg['ph__avg'],
            self._landscores_agg['cao__avg'],
            self._landscores_agg['mgo__avg'],
            self._landscores_agg['k2o__avg'],
            self._landscores_agg['base_saturation__avg'],
            self._landscores_agg['cao_per_mgo__avg'],
            self._landscores_agg['mgo_per_k2o__avg']
        ]
        chart2 = g.plot_graph("塩基類関連（1圃場の全エリア平均）", x, y)

        x = ['リン吸(mg/100g)', 'P2O5(mg/100g)', ' ', '  ', '   ', '    ', '     ']
        y = [
            self._landscores_agg['phosphorus_absorption__avg'],
            self._landscores_agg['p2o5__avg'],
            0,
            0,
            0,
            0,
            0
        ]
        chart3 = g.plot_graph("リン酸関連（1圃場の全エリア平均）", x, y)

        x = ['CEC(meq/100g)', '腐植(%)', '仮比重', ' ', '  ', '   ', '    ']
        y = [
            self._landscores_agg['cec__avg'],
            self._landscores_agg['humus__avg'],
            self._landscores_agg['bulk_density__avg'],
            0,
            0,
            0,
            0
        ]
        chart4 = g.plot_graph("土壌ポテンシャル関連（1圃場の全エリア平均）", x, y)

        return {
            'chart1': chart1,
            'chart2': chart2,
            'chart3': chart3,
            'chart4': chart4
        }
