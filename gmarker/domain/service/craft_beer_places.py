"""Google Places API からクラフトビール店の候補を抽出する処理。"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from django.utils import timezone


FIELD_MASK = (
    "places.id,places.displayName.text,places.formattedAddress,places.location,"
    "places.businessStatus,places.primaryType,places.types,places.rating,"
    "places.userRatingCount,places.googleMapsUri"
)
PLACES_API_URL = "https://places.googleapis.com/v1/places"
SUPPORTED_NEARBY_TYPES = frozenset({"bar", "pub", "restaurant"})
CLOSED_BUSINESS_STATUSES = frozenset({"CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"})


class PlacesApiError(Exception):
    """Google Places API の呼び出しまたはレスポンスが不正な場合の例外。"""


class RequiredPlaceMissingError(Exception):
    """設定した必須店舗が有効候補に含まれない場合の例外。"""


@dataclass(frozen=True)
class CraftBeerExportConfig:
    """クラフトビール候補抽出で使う検索条件と対象境界。"""

    area_name: str
    center_lat: float
    center_lng: float
    radius_meters: int
    bounds: dict[str, float]
    text_queries: list[str]
    nearby_types: list[str]
    language_code: str
    region_code: str
    required_place: dict[str, Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CraftBeerExportConfig:
        """JSON 設定を検証して抽出設定へ変換する。"""
        if not all(
            isinstance(value.get(key), list) for key in ("text_queries", "nearby_types")
        ) or not isinstance(value.get("required_place"), dict):
            raise ValueError(
                "text_queries と nearby_types は配列、required_place はオブジェクトにしてください。"
            )
        try:
            center = value["center"]
            bounds = value["bounds"]
            config = cls(
                area_name=str(value["area_name"]),
                center_lat=float(center["lat"]),
                center_lng=float(center["lng"]),
                radius_meters=int(value["radius_meters"]),
                bounds={
                    "south": float(bounds["south"]),
                    "north": float(bounds["north"]),
                    "west": float(bounds["west"]),
                    "east": float(bounds["east"]),
                },
                text_queries=[str(query) for query in value["text_queries"]],
                nearby_types=[str(place_type) for place_type in value["nearby_types"]],
                language_code=str(value.get("language_code", "ja")),
                region_code=str(value.get("region_code", "JP")),
                required_place=dict(value["required_place"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("抽出設定の必須項目または値が不正です。") from error

        if not config.area_name or not config.text_queries or not config.nearby_types:
            raise ValueError("area_name、text_queries、nearby_types は空にできません。")
        if not 500 <= config.radius_meters <= 800:
            raise ValueError("radius_meters は 500〜800 の範囲で指定してください。")
        if config.bounds["south"] >= config.bounds["north"]:
            raise ValueError("bounds の south は north より小さくしてください。")
        if config.bounds["west"] >= config.bounds["east"]:
            raise ValueError("bounds の west は east より小さくしてください。")

        invalid_types = set(config.nearby_types) - SUPPORTED_NEARBY_TYPES
        if invalid_types:
            raise ValueError(
                "Nearby Search で使えない type が指定されています: "
                f"{', '.join(sorted(invalid_types))}"
            )
        if not config.required_place.get(
            "name_terms"
        ) and not config.required_place.get("place_id"):
            raise ValueError(
                "required_place に name_terms または place_id が必要です。"
            )
        if not isinstance(config.required_place.get("name_terms", []), list):
            raise ValueError("required_place.name_terms は配列にしてください。")
        return config

    def public_dict(self) -> dict[str, Any]:
        """秘密情報を含めずに出力できる検索条件を返す。"""
        return {
            "area_name": self.area_name,
            "center": {"lat": self.center_lat, "lng": self.center_lng},
            "radius_meters": self.radius_meters,
            "bounds": self.bounds,
            "text_queries": self.text_queries,
            "nearby_types": self.nearby_types,
            "language_code": self.language_code,
            "region_code": self.region_code,
            "required_place": self.required_place,
        }


def load_config(config_path: str | Path) -> CraftBeerExportConfig:
    """JSON ファイルを読み込み、クラフトビール抽出設定として検証する。"""
    try:
        with Path(config_path).open(encoding="utf-8") as config_file:
            value = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"設定ファイルを読み込めません: {config_path}") from error
    if not isinstance(value, dict):
        raise ValueError("設定ファイルの最上位要素はオブジェクトにしてください。")
    return CraftBeerExportConfig.from_dict(value)


class PlacesApiClient:
    """Places API (New) の Text Search と Nearby Search を呼ぶクライアント。"""

    def __init__(self, api_key: str, timeout_seconds: int = 20):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search_text(
        self, *, query: str, config: CraftBeerExportConfig
    ) -> list[dict[str, Any]]:
        """検索語で Text Search を一回実行して places 配列を返す。"""
        return self._post(
            endpoint=":searchText",
            body={
                "textQuery": query,
                "locationBias": self._circle(config),
                "languageCode": config.language_code,
                "regionCode": config.region_code,
            },
        )

    def search_nearby(
        self, *, place_type: str, config: CraftBeerExportConfig
    ) -> list[dict[str, Any]]:
        """type ごとに Nearby Search を一回実行して places 配列を返す。"""
        return self._post(
            endpoint=":searchNearby",
            body={
                "includedTypes": [place_type],
                "locationRestriction": self._circle(config),
                "languageCode": config.language_code,
            },
        )

    @staticmethod
    def _circle(config: CraftBeerExportConfig) -> dict[str, Any]:
        return {
            "circle": {
                "center": {
                    "latitude": config.center_lat,
                    "longitude": config.center_lng,
                },
                "radius": config.radius_meters,
            }
        }

    def _post(self, *, endpoint: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            response = requests.post(
                f"{PLACES_API_URL}{endpoint}",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": FIELD_MASK,
                },
                json=body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise PlacesApiError(
                f"Places API {endpoint} の呼び出しに失敗しました。"
            ) from error

        places = payload.get("places") if isinstance(payload, dict) else None
        if not isinstance(places, list) or not all(
            isinstance(place, dict) for place in places
        ):
            raise PlacesApiError(
                f"Places API {endpoint} のレスポンスに places 配列がありません。"
            )
        return places


class CraftBeerPlacesExporter:
    """検索結果を統合し、掲載候補・手動確認・除外へ分類する。"""

    def __init__(self, client: PlacesApiClient):
        self.client = client

    def collect(self, config: CraftBeerExportConfig) -> dict[str, Any]:
        """全検索を実行し、重複を除いた検品用の抽出結果を返す。"""
        retrieved_at = timezone.now().isoformat()
        merged: dict[str, dict[str, Any]] = {}

        for query in config.text_queries:
            self._merge_places(
                merged=merged,
                places=self.client.search_text(query=query, config=config),
                matched_query=f"keyword:{query}",
            )
        for place_type in config.nearby_types:
            self._merge_places(
                merged=merged,
                places=self.client.search_nearby(place_type=place_type, config=config),
                matched_query=f"type:{place_type}",
            )

        result = {"candidates": [], "manual_review": [], "excluded": []}
        for place in merged.values():
            record = self._record(place=place, retrieved_at=retrieved_at)
            group, reason = self._classify(record=record, config=config)
            record["result_category"] = group
            if reason:
                record["exclusion_reason"] = reason
            result[group].append(record)

        self._check_required_place(candidates=result["candidates"], config=config)
        return {
            "area_name": config.area_name,
            "retrieved_at": retrieved_at,
            "search_conditions": config.public_dict(),
            "counts": {key: len(records) for key, records in result.items()},
            **result,
        }

    @staticmethod
    def _merge_places(
        *,
        merged: dict[str, dict[str, Any]],
        places: list[dict[str, Any]],
        matched_query: str,
    ) -> None:
        for place in places:
            place_id = place.get("id")
            if not isinstance(place_id, str) or not place_id:
                raise PlacesApiError(
                    "Places API の結果に必須の places.id がありません。"
                )
            existing = merged.setdefault(place_id, {**place, "matched_queries": []})
            if matched_query not in existing["matched_queries"]:
                existing["matched_queries"].append(matched_query)

    @staticmethod
    def _record(*, place: dict[str, Any], retrieved_at: str) -> dict[str, Any]:
        location = place.get("location")
        name = place.get("displayName")
        matched_queries = place["matched_queries"]
        has_keyword = any(query.startswith("keyword:") for query in matched_queries)
        has_type = any(query.startswith("type:") for query in matched_queries)
        candidate_category = (
            "keyword_and_type"
            if has_keyword and has_type
            else "keyword" if has_keyword else "type"
        )
        return {
            "place_id": place["id"],
            "name": name.get("text", "") if isinstance(name, dict) else "",
            "formatted_address": place.get("formattedAddress"),
            "location": (
                {
                    "lat": location.get("latitude"),
                    "lng": location.get("longitude"),
                }
                if isinstance(location, dict)
                else None
            ),
            "business_status": place.get("businessStatus"),
            "primary_type": place.get("primaryType"),
            "types": place.get("types", []),
            "rating": place.get("rating"),
            "user_rating_count": place.get("userRatingCount"),
            "google_maps_uri": place.get("googleMapsUri"),
            "matched_queries": matched_queries,
            "candidate_category": candidate_category,
            "manual_review_required": True,
            "craft_beer_specialty": "unconfirmed",
            "tap_count": None,
            "publication_permission": "unconfirmed",
            "reviewer_note": "",
            "retrieved_at": retrieved_at,
        }

    @staticmethod
    def _classify(
        *, record: dict[str, Any], config: CraftBeerExportConfig
    ) -> tuple[str, str | None]:
        location = record["location"]
        if not location or location["lat"] is None or location["lng"] is None:
            return "excluded", "location_missing"
        if not CraftBeerPlacesExporter._is_inside_bounds(location, config.bounds):
            return "excluded", "outside_target_area"
        if record["business_status"] in CLOSED_BUSINESS_STATUSES:
            return "excluded", "business_closed"
        if record["business_status"] != "OPERATIONAL":
            return "manual_review", "business_status_unknown"
        if not any(query.startswith("keyword:") for query in record["matched_queries"]):
            return "manual_review", "type_search_only"
        return "candidates", None

    @staticmethod
    def _is_inside_bounds(location: dict[str, float], bounds: dict[str, float]) -> bool:
        return (
            bounds["south"] <= location["lat"] <= bounds["north"]
            and bounds["west"] <= location["lng"] <= bounds["east"]
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", value).casefold())

    def _check_required_place(
        self, *, candidates: list[dict[str, Any]], config: CraftBeerExportConfig
    ) -> None:
        required = config.required_place
        expected_id = required.get("place_id")
        name_terms = [self._normalize(term) for term in required.get("name_terms", [])]
        address_hint = self._normalize(required.get("address_hint", ""))

        for candidate in candidates:
            id_matches = not expected_id or candidate["place_id"] == expected_id
            name_matches = bool(expected_id) or any(
                term in self._normalize(candidate["name"]) for term in name_terms
            )
            address_matches = not address_hint or address_hint in self._normalize(
                candidate["formatted_address"] or ""
            )
            if id_matches and name_matches and address_matches:
                return

        raise RequiredPlaceMissingError(
            "必須候補 TAP&CROWLER Shibuya を、営業中かつ対象エリア内の候補として確認できませんでした。"
        )


def write_output(
    *, result: dict[str, Any], output_path: str | Path, output_format: str
) -> None:
    """抽出結果を JSON または CSV へ書き出す。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        with path.open("w", encoding="utf-8", newline="") as output_file:
            json.dump(result, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
        return
    if output_format != "csv":
        raise ValueError("output_format は json または csv を指定してください。")

    rows = [
        _flatten_record(record)
        for group in ("candidates", "manual_review", "excluded")
        for record in result[group]
    ]
    fieldnames = [
        "result_category",
        "exclusion_reason",
        "place_id",
        "name",
        "formatted_address",
        "location_lat",
        "location_lng",
        "business_status",
        "primary_type",
        "types",
        "rating",
        "user_rating_count",
        "google_maps_uri",
        "matched_queries",
        "candidate_category",
        "manual_review_required",
        "craft_beer_specialty",
        "tap_count",
        "publication_permission",
        "reviewer_note",
        "retrieved_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    """ネストした候補レコードを CSV の一行へ変換する。"""
    location = record.get("location") or {}
    return {
        **{key: value for key, value in record.items() if key != "location"},
        "location_lat": location.get("lat"),
        "location_lng": location.get("lng"),
        "types": json.dumps(record["types"], ensure_ascii=False),
        "matched_queries": json.dumps(record["matched_queries"], ensure_ascii=False),
    }
