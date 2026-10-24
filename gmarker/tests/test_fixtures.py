from django.core.management import call_command
from django.test import TransactionTestCase

from gmarker.models import NearbyPlace, Place


class GMarkerFixtureTest(TransactionTestCase):
    def test_fixtures_keep_nearby_place_references_after_sequence_advance(self):
        """
        シナリオ:
        - 入力: auto increment の次の値が 2 になるように一時的な Place を登録して削除する。
        - 処理: Place と NearbyPlace の fixture をまとめて読み込む。
        - 期待値: Place の主キーが 1, 2, 3 に固定され、NearbyPlace の参照先が一致する。
        """
        temporary_place = Place.objects.create(
            place_id="temporary-place-id",
            name="Temporary place",
            location="0,0",
        )
        temporary_place.delete()

        call_command(
            "loaddata",
            "gmarker/fixtures/place.json",
            "gmarker/fixtures/nearbyPlace.json",
            verbosity=0,
        )

        self.assertEqual(
            list(Place.objects.order_by("pk").values_list("pk", flat=True)),
            [1, 2, 3],
        )
        self.assertEqual(
            list(NearbyPlace.objects.order_by("pk").values_list("place_id", flat=True)),
            [1, 2, 3],
        )
