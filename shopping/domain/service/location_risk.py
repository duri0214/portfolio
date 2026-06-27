from shopping.domain.valueobject.location_risk import (
    EntryRateScenario,
    ExpectedVisitorEstimate,
    LocationRiskAssessment,
)


class LocationRiskService:
    """単一地点の店前通行量から、通りすがり集客の期待値を評価する。"""

    DEFAULT_SCENARIOS = [
        EntryRateScenario(label="保守的", rate_percent=0.5),
        EntryRateScenario(label="標準", rate_percent=1.0),
        EntryRateScenario(label="強気", rate_percent=2.0),
    ]

    @classmethod
    def assess(
        cls,
        pedestrian_count_per_hour: int,
        scenarios: list[EntryRateScenario] | None = None,
    ) -> LocationRiskAssessment:
        selected_scenarios = scenarios or cls.DEFAULT_SCENARIOS
        estimates = [
            ExpectedVisitorEstimate(
                label=scenario.label,
                entry_rate_percent=scenario.rate_percent,
                visitors_per_hour=round(pedestrian_count_per_hour * scenario.rate, 2),
            )
            for scenario in selected_scenarios
        ]

        strongest_estimate = max(
            estimates, key=lambda estimate: estimate.visitors_per_hour
        )
        if strongest_estimate.visitors_per_hour < 1:
            risk_label = "通りすがり依存は厳しい"
            recommendation = "目的来店、SNS、地域コミュニティ導線を優先する"
        elif strongest_estimate.visitors_per_hour < 3:
            risk_label = "通りすがりだけでは弱い"
            recommendation = "店前施策と指名来店施策を併用する"
        else:
            risk_label = "店前施策の検証余地あり"
            recommendation = "看板、外観、時間帯別訴求を検証する"

        return LocationRiskAssessment(
            pedestrian_count_per_hour=pedestrian_count_per_hour,
            estimates=estimates,
            risk_label=risk_label,
            recommendation=recommendation,
        )
