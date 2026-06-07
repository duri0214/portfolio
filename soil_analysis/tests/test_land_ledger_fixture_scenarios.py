import json
from pathlib import Path

from django.test import SimpleTestCase


class LandLedgerFixtureScenarioTest(SimpleTestCase):
    def test_fixture_has_current_and_next_year_sowing_and_harvest_scenarios(self):
        """
        シナリオ:
        - 入力: userattribute.json, company.json, crop.json, land.json, land_period.json, land_ledger.json の fixture。
        - 処理: 点検用オーナー属性、テスト会社・テスト作物・FIELD001〜FIELD003 と、今年度(2026)播種時、今年度(2026)収穫時、来年度(2027)播種時、来年度(2027)収穫時の台帳を抽出する。
        - 期待値: 点検用のユーザー属性・会社・作物・圃場が存在し、2025年以前の古い期間・台帳と既存の農業法人会社を含まず、FIELD001〜FIELD003 について4シナリオすべての台帳がテスト作物で作成されていること。
        """
        fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
        user_attributes = self._load_fixture(fixture_dir / "userattribute.json")
        companies = self._load_fixture(fixture_dir / "company.json")
        crops = self._load_fixture(fixture_dir / "crop.json")
        lands = self._load_fixture(fixture_dir / "land.json")
        periods = self._load_fixture(fixture_dir / "land_period.json")
        ledgers = self._load_fixture(fixture_dir / "land_ledger.json")

        self.assertEqual(
            {
                item["fields"]["user"]: (
                    item["fields"]["role"],
                    item["fields"]["organization"],
                )
                for item in user_attributes
                if item["fields"]["user"] in {21, 22}
            },
            {
                21: ("owner", "土壌分析テスト法人"),
                22: ("owner", "土壌分析テスト法人"),
            },
        )
        self.assertIn(
            (1, "土壌分析テスト法人"),
            {(item["fields"]["id"], item["fields"]["name"]) for item in companies},
        )
        self.assertEqual(
            [
                item["fields"]["id"]
                for item in companies
                if item["fields"]["category"] == 1
            ],
            [1],
        )
        self.assertIn(
            (3, "点検用テスト作物"),
            {(item["fields"]["id"], item["fields"]["name"]) for item in crops},
        )
        self.assertEqual(
            {
                item["fields"]["id"]: item["fields"]["name"]
                for item in lands
                if item["fields"]["id"] in {1, 2, 3}
            },
            {
                1: "FIELD001（点検用圃場）",
                2: "FIELD002（点検用圃場）",
                3: "FIELD003（点検用圃場）",
            },
        )

        period_ids = {
            (item["fields"]["year"], item["fields"]["name"]): item["fields"]["id"]
            for item in periods
        }
        self.assertEqual(
            [item["fields"]["id"] for item in periods],
            list(range(1, 7)),
        )
        self.assertEqual(
            {item["fields"]["year"] for item in periods},
            {2026, 2027},
        )
        ledger_keys = {
            (
                item["fields"]["land_id"],
                item["fields"]["land_period_id"],
                item["fields"]["crop_id"],
            )
            for item in ledgers
        }

        inspection_scenarios = [
            (2026, "播種時"),
            (2026, "収穫時"),
            (2027, "播種時"),
            (2027, "収穫時"),
        ]
        inspection_land_ids = [1, 2, 3]

        for year, period_name in inspection_scenarios:
            period_id = period_ids[(year, period_name)]
            for land_id in inspection_land_ids:
                self.assertIn((land_id, period_id, 3), ledger_keys)

        self.assertTrue(
            [item["fields"]["id"] for item in ledgers] == list(range(1, 13))
        )

    @staticmethod
    def _load_fixture(path: Path) -> list[dict]:
        with path.open(encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
