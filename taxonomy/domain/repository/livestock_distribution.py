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
        return LivestockDistributionDatasetRepository._build_dashboard(dataset)

    @staticmethod
    def get_dashboard_by_survey_year(
        survey_year: int,
    ) -> LivestockDistributionDashboard | None:
        """
        指定した対象年の有効な畜産統計CSVからダッシュボードを返します。
        """
        dataset = LivestockDistributionDataset.objects.filter(
            is_active=True,
            survey_year=survey_year,
        ).first()
        return LivestockDistributionDatasetRepository._build_dashboard(dataset)

    @staticmethod
    def get_active_survey_years() -> list[int]:
        """
        画面で切り替え可能な有効データセットの対象年一覧を返します。
        """
        datasets = LivestockDistributionDataset.objects.filter(is_active=True).only(
            "csv_file", "survey_year"
        )
        years = [
            dataset.survey_year
            for dataset in datasets
            if LivestockDistributionDatasetRepository._has_csv_file(dataset)
        ]
        return sorted(set(years), reverse=True)

    @staticmethod
    def _build_dashboard(
        dataset: LivestockDistributionDataset | None,
    ) -> LivestockDistributionDashboard | None:
        """
        畜産統計CSVデータセットから表示用ダッシュボードを組み立てます。
        """
        if dataset is None:
            return None
        if not LivestockDistributionDatasetRepository._has_csv_file(dataset):
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

    @staticmethod
    def _has_csv_file(dataset: LivestockDistributionDataset) -> bool:
        if not dataset.csv_file:
            return False
        return dataset.csv_file.storage.exists(dataset.csv_file.name)
