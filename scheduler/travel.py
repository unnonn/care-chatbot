"""Google Maps Distance Matrix API で2地点間の移動時間を取得する。

- オンライン同士、または同一場所どうしは 0 分。
- 物理的な場所2点なら Maps を叩き、結果はメモリにキャッシュ。
- Maps API キー未設定 / 呼び出し失敗時は FALLBACK_TRAVEL_MIN を返す。
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

from scheduler.config import (
    FALLBACK_TRAVEL_MIN,
    LOCATIONS,
    TRAVEL_CACHE_TTL_SEC,
    Location,
    maps_api_key,
)

log = logging.getLogger(__name__)

_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# (origin_key, destination_key) -> (minutes, expires_at_epoch)
_cache: dict[tuple[str, str], tuple[int, float]] = {}
_cache_lock = threading.Lock()


def _fallback(origin: Location, destination: Location) -> int:
    if origin.key == destination.key:
        return 0
    if origin.is_online or destination.is_online:
        return 0
    key = frozenset({origin.key, destination.key})
    return FALLBACK_TRAVEL_MIN.get(key, 60)


def _cache_get(origin_key: str, dest_key: str) -> int | None:
    with _cache_lock:
        hit = _cache.get((origin_key, dest_key))
        if hit and hit[1] > time.time():
            return hit[0]
    return None


def _cache_put(origin_key: str, dest_key: str, minutes: int) -> None:
    with _cache_lock:
        _cache[(origin_key, dest_key)] = (minutes, time.time() + TRAVEL_CACHE_TTL_SEC)


def _maps_lookup(origin: Location, destination: Location) -> int | None:
    api_key = maps_api_key()
    if not api_key:
        return None
    try:
        resp = httpx.get(
            _DISTANCE_MATRIX_URL,
            params={
                "origins": origin.address,
                "destinations": destination.address,
                "mode": "transit",
                "language": "ja",
                "region": "jp",
                "key": api_key,
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Distance Matrix request failed: %s", exc)
        return None

    if data.get("status") != "OK":
        log.warning("Distance Matrix top-level status not OK: %s", data.get("status"))
        return None

    try:
        element = data["rows"][0]["elements"][0]
    except (KeyError, IndexError):
        return None

    if element.get("status") != "OK":
        log.info(
            "Distance Matrix element status %s for %s -> %s",
            element.get("status"),
            origin.key,
            destination.key,
        )
        return None

    seconds = element["duration"]["value"]
    # 余裕分として乗り換えバッファ +10 分を上乗せ。
    return int(seconds // 60) + 10


def travel_minutes(origin: Location | str, destination: Location | str) -> int:
    """2地点間の必要移動時間（分）。オンラインや同一拠点なら 0。"""
    if isinstance(origin, str):
        origin = LOCATIONS[origin]
    if isinstance(destination, str):
        destination = LOCATIONS[destination]

    if origin.key == destination.key:
        return 0
    if origin.is_online or destination.is_online:
        return 0

    cached = _cache_get(origin.key, destination.key)
    if cached is not None:
        return cached

    minutes = _maps_lookup(origin, destination)
    if minutes is None:
        minutes = _fallback(origin, destination)

    _cache_put(origin.key, destination.key, minutes)
    return minutes
