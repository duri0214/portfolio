"""Google Places API を使った候補検索プロファイルの処理。"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone


FIELD_MASK = (
    "places.id,places.displayName.text,places.formattedAddress,places.location,"
    "places.businessStatus,places.primaryType,places.types,places.rating,"
    "places.userRatingCount,places.googleMapsUri"
)
FIELD_MASK_WITH_REVIEWS = f"{FIELD_MASK},places.reviews"
PLACES_API_URL = "https://places.googleapis.com/v1/places"
CLOSED_BUSINESS_STATUSES = frozenset({"CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"})


class PlacesApiError(Exception):
    """Places API の呼び出しまたはレスポンス検証に失敗したことを表す。"""


class RequiredPlaceMissingError(Exception):
    """必須店舗が営業中の候補として見つからないことを表す。"""


class CriteriaNotFoundError(LookupError):
    """指定された候補検索プロファイルがカタログにないことを表す。"""


@dataclass(frozen=True)
class RequiredPlaceCriteria:
    """候補結果に含まれていることを確認する店舗条件。

    Attributes:
        place_id: Google Place ID で照合する場合の ID。
        name_terms: 店舗名に含まれることを確認する語句。
        address_hint: 住所に含まれることを確認する語句。
    """

    place_id: str | None
    name_terms: list[str]
    address_hint: str

    @classmethod
    def from_dict(cls, value: Any) -> RequiredPlaceCriteria:
        """JSON の必須店舗条件を検証して値オブジェクトへ変換する。"""
        if not isinstance(value, dict):
            raise ValueError("required_place はオブジェクトで指定してください")

        place_id = value.get("place_id")
        if place_id is not None and (
            not isinstance(place_id, str) or not place_id.strip()
        ):
            raise ValueError(
                "required_place.place_id は空でない文字列で指定してください"
            )

        name_terms = value.get("name_terms", [])
        if not isinstance(name_terms, list) or not all(
            isinstance(term, str) and term.strip() for term in name_terms
        ):
            raise ValueError(
                "required_place.name_terms は空でない文字列の配列で指定してください"
            )

        address_hint = value.get("address_hint", "")
        if not isinstance(address_hint, str):
            raise ValueError("required_place.address_hint は文字列で指定してください")

        if not place_id and not name_terms:
            raise ValueError(
                "required_place には place_id または name_terms が必要です"
            )

        return cls(
            place_id=place_id.strip() if place_id else None,
            name_terms=[term.strip() for term in name_terms],
            address_hint=address_hint.strip(),
        )


@dataclass(frozen=True)
class PlaceSearchCriteria:
    """候補店舗を検索・分類するためのプロファイル。

    Attributes:
        slug: URL とカタログ解決に使う一意な識別子。
        label: 画面のボタンと見出しに表示する名称。
        area_name: 検索結果を識別する内部名称。
        center_lat: Places API の検索中心の緯度。
        center_lng: Places API の検索中心の経度。
        radius_meters: 検索円の半径（メートル）。
        bounds: 候補を含める矩形境界。
        text_queries: Text Search に渡す検索語。
        nearby_types: Nearby Search に渡す Place type。
        language_code: Places API の言語コード。
        region_code: Places API の地域コード。
        include_type_only: type 検索だけで見つかった店舗を候補に含めるか。
        required_place: 任意の必須店舗条件。
    """

    slug: str
    label: str
    area_name: str
    center_lat: float
    center_lng: float
    radius_meters: int
    bounds: dict[str, float]
    text_queries: list[str]
    nearby_types: list[str]
    language_code: str
    region_code: str
    include_type_only: bool
    required_place: RequiredPlaceCriteria | None

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        *,
        slug: str | None = None,
        label: str | None = None,
    ) -> PlaceSearchCriteria:
        """JSON の候補検索条件を検証してプロファイルへ変換する。"""
        if not isinstance(value, dict):
            raise ValueError("候補検索条件の最上位はオブジェクトで指定してください")

        resolved_slug = slug or value.get("slug")
        resolved_label = label or value.get("label")
        if not isinstance(resolved_slug, str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", resolved_slug
        ):
            raise ValueError("slug は小文字・数字・ハイフンで指定してください")
        if not isinstance(resolved_label, str) or not resolved_label.strip():
            raise ValueError("label は空でない文字列で指定してください")

        try:
            center = value["center"]
            bounds = value["bounds"]
            area_name = str(value.get("area_name", resolved_slug)).strip()
            center_lat = float(center["lat"])
            center_lng = float(center["lng"])
            radius_meters = int(value["radius_meters"])
            parsed_bounds = {
                "south": float(bounds["south"]),
                "north": float(bounds["north"]),
                "west": float(bounds["west"]),
                "east": float(bounds["east"]),
            }
            text_queries = value["text_queries"]
            nearby_types = value["nearby_types"]
            language_code = str(value.get("language_code", "ja")).strip()
            region_code = str(value.get("region_code", "JP")).strip()
            include_type_only = value.get("include_type_only", False)
            required_place_value = value.get("required_place")
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("候補検索条件の必須項目または値が不正です") from error

        if not area_name:
            raise ValueError("area_name は空にできません")
        if not isinstance(center, dict) or not isinstance(bounds, dict):
            raise ValueError("center と bounds はオブジェクトで指定してください")
        if radius_meters <= 0:
            raise ValueError("radius_meters は正の整数で指定してください")
        if parsed_bounds["south"] >= parsed_bounds["north"]:
            raise ValueError("bounds の south は north より小さくしてください")
        if parsed_bounds["west"] >= parsed_bounds["east"]:
            raise ValueError("bounds の west は east より小さくしてください")
        if not isinstance(text_queries, list) or not all(
            isinstance(query, str) and query.strip() for query in text_queries
        ):
            raise ValueError("text_queries は空でない文字列の配列で指定してください")
        if not isinstance(nearby_types, list) or not all(
            isinstance(place_type, str) and place_type.strip()
            for place_type in nearby_types
        ):
            raise ValueError("nearby_types は空でない文字列の配列で指定してください")
        if not text_queries and not nearby_types:
            raise ValueError(
                "text_queries または nearby_types を一つ以上指定してください"
            )
        if not language_code or not region_code:
            raise ValueError("language_code と region_code は空にできません")
        if not isinstance(include_type_only, bool):
            raise ValueError("include_type_only は真偽値で指定してください")

        required_place = (
            RequiredPlaceCriteria.from_dict(required_place_value)
            if required_place_value is not None
            else None
        )
        return cls(
            slug=resolved_slug,
            label=resolved_label.strip(),
            area_name=area_name,
            center_lat=center_lat,
            center_lng=center_lng,
            radius_meters=radius_meters,
            bounds=parsed_bounds,
            text_queries=[query.strip() for query in text_queries],
            nearby_types=[place_type.strip() for place_type in nearby_types],
            language_code=language_code,
            region_code=region_code,
            include_type_only=include_type_only,
            required_place=required_place,
        )


class PlaceSearchCriteriaCatalog:
    """criteria ディレクトリから候補検索プロファイルを解決するカタログ。"""

    def __init__(self, criteria_directory: str | Path | None = None):
        self.criteria_directory = Path(
            criteria_directory or settings.BASE_DIR / "gmarker/criteria"
        )

    def all(self) -> list[PlaceSearchCriteria]:
        """登録済みの候補検索プロファイルをファイル名順で返す。"""
        paths = sorted(self.criteria_directory.glob("*.json"))
        if not paths:
            raise ValueError("候補検索 criteria が一つも登録されていません")

        criteria_list = [self._load(path) for path in paths]
        slugs = [criteria.slug for criteria in criteria_list]
        if len(slugs) != len(set(slugs)):
            raise ValueError("候補検索 criteria の slug が重複しています")
        return criteria_list

    def resolve(self, slug: str) -> PlaceSearchCriteria:
        """URL の slug に一致する候補検索プロファイルを返す。"""
        for criteria in self.all():
            if criteria.slug == slug:
                return criteria
        raise CriteriaNotFoundError(slug)

    def _load(self, path: Path) -> PlaceSearchCriteria:
        try:
            with path.open(encoding="utf-8") as criteria_file:
                value = json.load(criteria_file)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"候補検索 criteria を読み込めません: {path}") from error
        return PlaceSearchCriteria.from_dict(
            value,
            slug=(
                value.get("slug", path.stem.replace("_", "-"))
                if isinstance(value, dict)
                else None
            ),
            label=value.get("label") if isinstance(value, dict) else None,
        )


class PlacesApiClient:
    """Places API (New) の Text Search と Nearby Search を呼び出すクライアント。"""

    def __init__(
        self,
        api_key: str,
        timeout_seconds: int = 20,
        field_mask: str = FIELD_MASK,
    ):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.field_mask = field_mask

    def search_text(
        self, *, query: str, criteria: PlaceSearchCriteria
    ) -> list[dict[str, Any]]:
        """検索語を使って Text Search を一回実行する。"""
        return self._post(
            endpoint=":searchText",
            body={
                "textQuery": query,
                "locationBias": self._circle(criteria),
                "languageCode": criteria.language_code,
                "regionCode": criteria.region_code,
            },
        )

    def search_nearby(
        self, *, place_type: str, criteria: PlaceSearchCriteria
    ) -> list[dict[str, Any]]:
        """Place type を使って Nearby Search を一回実行する。"""
        return self._post(
            endpoint=":searchNearby",
            body={
                "includedTypes": [place_type],
                "locationRestriction": self._circle(criteria),
                "languageCode": criteria.language_code,
                "regionCode": criteria.region_code,
            },
        )

    @staticmethod
    def _circle(criteria: PlaceSearchCriteria) -> dict[str, Any]:
        return {
            "circle": {
                "center": {
                    "latitude": criteria.center_lat,
                    "longitude": criteria.center_lng,
                },
                "radius": criteria.radius_meters,
            }
        }

    def _post(self, *, endpoint: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            response = requests.post(
                f"{PLACES_API_URL}{endpoint}",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": self.field_mask,
                },
                json=body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise PlacesApiError(
                f"Places API {endpoint} の呼び出しに失敗しました"
            ) from error

        places = payload.get("places") if isinstance(payload, dict) else None
        if not isinstance(places, list) or not all(
            isinstance(place, dict) for place in places
        ):
            raise PlacesApiError(
                f"Places API {endpoint} のレスポンスに places 配列がありません"
            )
        return places


class PlaceCandidateFilter:
    """検索結果を統合し、criteria に従って候補・手動確認・除外へ分類する。"""

    def __init__(self, client: PlacesApiClient):
        self.client = client

    def collect(
        self, criteria: PlaceSearchCriteria, *, include_reviews: bool = False
    ) -> dict[str, Any]:
        """criteria の検索経路を実行し、分類済み店舗と件数を返す。

        Args:
            criteria: 検索語、検索範囲、分類ルールを含むプロファイル。
            include_reviews: 画面表示用に Places API のレビューを含めるか。

        Returns:
            候補、手動確認、除外の店舗一覧と各件数。
        """
        retrieved_at = timezone.now().isoformat()
        merged: dict[str, dict[str, Any]] = {}

        for query in criteria.text_queries:
            self._merge_places(
                merged=merged,
                places=self.client.search_text(query=query, criteria=criteria),
                matched_query=f"keyword:{query}",
            )
        for place_type in criteria.nearby_types:
            self._merge_places(
                merged=merged,
                places=self.client.search_nearby(
                    place_type=place_type, criteria=criteria
                ),
                matched_query=f"type:{place_type}",
            )

        result = {"candidates": [], "manual_review": [], "excluded": []}
        for place in merged.values():
            record = self._record(
                place=place,
                retrieved_at=retrieved_at,
                include_reviews=include_reviews,
            )
            group, reason = self._classify(record=record, criteria=criteria)
            record["result_category"] = group
            if reason:
                record["exclusion_reason"] = reason
            result[group].append(record)

        self._check_required_place(candidates=result["candidates"], criteria=criteria)
        return {
            "criteria_slug": criteria.slug,
            "label": criteria.label,
            "area_name": criteria.area_name,
            "counts": {key: len(records) for key, records in result.items()},
            **result,
        }

    @staticmethod
    def to_display_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """画面と地図に必要な店舗項目だけを返す。

        検索語、検索経路、type 判定などの検品情報は画面へ渡さない。
        """
        display_keys = {
            "place_id",
            "name",
            "formatted_address",
            "location",
            "rating",
            "google_maps_uri",
            "reviews",
        }
        return [
            {key: value for key, value in record.items() if key in display_keys}
            for record in records
        ]

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
                raise PlacesApiError("Places API の結果に places.id がありません")
            existing = merged.setdefault(place_id, {**place, "matched_queries": []})
            if matched_query not in existing["matched_queries"]:
                existing["matched_queries"].append(matched_query)

    @staticmethod
    def _record(
        *, place: dict[str, Any], retrieved_at: str, include_reviews: bool
    ) -> dict[str, Any]:
        location = place.get("location")
        matched_queries = place["matched_queries"]
        has_keyword = any(query.startswith("keyword:") for query in matched_queries)
        has_type = any(query.startswith("type:") for query in matched_queries)
        candidate_category = (
            "keyword_and_type"
            if has_keyword and has_type
            else "keyword" if has_keyword else "type"
        )
        record = {
            "place_id": place["id"],
            "name": (
                place.get("displayName", {}).get("text", "")
                if isinstance(place.get("displayName"), dict)
                else ""
            ),
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
            "publication_permission": "unconfirmed",
            "reviewer_note": "",
            "retrieved_at": retrieved_at,
        }
        if include_reviews:
            record["reviews"] = PlaceCandidateFilter._reviews(place.get("reviews"))
        return record

    @staticmethod
    def _reviews(value: Any) -> list[dict[str, str | None]]:
        """Places API のレビューを画面表示用の項目へ整形する。"""
        if not isinstance(value, list):
            return []
        return [
            {
                "review_text": review.get("text", {}).get("text"),
                "author": review.get("authorAttribution", {}).get("displayName"),
                "publish_time": review.get("publishTime"),
                "google_maps_uri": review.get("googleMapsUri"),
            }
            for review in value
            if isinstance(review, dict)
        ][:5]

    def _classify(
        self, *, record: dict[str, Any], criteria: PlaceSearchCriteria
    ) -> tuple[str, str | None]:
        location = record["location"]
        if not location or location["lat"] is None or location["lng"] is None:
            return "excluded", "location_missing"
        if not self._is_inside_bounds(location, criteria.bounds):
            return "excluded", "outside_target_area"
        if record["business_status"] in CLOSED_BUSINESS_STATUSES:
            return "excluded", "business_closed"
        if record["business_status"] != "OPERATIONAL":
            return "manual_review", "business_status_unknown"
        if (
            not any(query.startswith("keyword:") for query in record["matched_queries"])
            and not criteria.include_type_only
        ):
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
        self,
        *,
        candidates: list[dict[str, Any]],
        criteria: PlaceSearchCriteria,
    ) -> None:
        required = criteria.required_place
        if required is None:
            return

        expected_id = required.place_id
        name_terms = [self._normalize(term) for term in required.name_terms]
        address_hint = self._normalize(required.address_hint)

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
            f"criteria {criteria.slug} の必須店舗が候補に見つかりません"
        )
