from io import TextIOWrapper

from taxonomy.domain.valueobject.livestock_distribution import (
    LivestockDistributionDashboard,
    LivestockDistributionSource,
    build_livestock_distribution_dashboard_from_rows,
    load_livestock_distribution_rows,
)
from taxonomy.models import LivestockDistributionDataset


class LivestockDistributionDatasetRepository:
    """
    e-Stat畜産統計CSVデータセットの永続化とファイル読み込みを扱うRepository。
    """

    @staticmethod
    def get_latest_dashboard() -> LivestockDistributionDashboard | None:
        """
        最新の有効な畜産統計CSVからダッシュボードを返します。
        """
        dataset = LivestockDistributionDataset.objects.filter(is_active=True).first()
        if dataset is None:
            return None

        source = LivestockDistributionSource(
            source_name=dataset.source_name,
            source_stat_code=dataset.source_stat_code,
            survey_year=dataset.survey_year,
            retrieved_at=dataset.retrieved_at,
            source_url=dataset.source_url,
            note=dataset.note,
        )
        with dataset.csv_file.open("rb") as binary_file:
            with TextIOWrapper(binary_file, encoding="utf-8", newline="") as text_file:
                rows = load_livestock_distribution_rows(text_file)

        return build_livestock_distribution_dashboard_from_rows(source, rows)
