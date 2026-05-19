"""場所定義・営業時間など、スケジューラの設定をまとめて保持。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Location:
    key: str
    label: str
    address: str
    keywords: tuple[str, ...]
    is_online: bool = False


# 3つの仕事場 + オンライン。
# keywords は Google カレンダー側の location 文字列を場所推定するためのヒント。
LOCATIONS: dict[str, Location] = {
    "bentencho": Location(
        key="bentencho",
        label="弁天町オフィス",
        address="〒552-0007 大阪府大阪市港区弁天1丁目, Japan",
        keywords=("弁天町", "弁天", "ベンテンチョウ", "Bentencho"),
    ),
    "umeda": Location(
        key="umeda",
        label="梅田オフィス",
        address="〒530-0001 大阪府大阪市北区梅田, Japan",
        keywords=("梅田", "Umeda", "大阪駅", "グランフロント"),
    ),
    "basecamp": Location(
        key="basecamp",
        label="近畿大学 Basecamp",
        address="近畿大学アカデミックシアター, 〒577-8502 大阪府東大阪市小若江3-4-1",
        keywords=("近畿大学", "近大", "Basecamp", "ベースキャンプ", "アカデミックシアター"),
    ),
    "online": Location(
        key="online",
        label="オンライン（Google Meet）",
        address="online",
        keywords=("meet.google.com", "zoom.us", "teams.microsoft.com", "オンライン", "ウェブ会議"),
        is_online=True,
    ),
}


def location_choices() -> list[Location]:
    """フォームに並べる場所選択肢（表示順）。"""
    return [LOCATIONS["bentencho"], LOCATIONS["umeda"], LOCATIONS["basecamp"], LOCATIONS["online"]]


# 営業時間（曜日: 0=月 ... 6=日）。
# 開始/終了は HH:MM 文字列、休みの日はキー無しで表現。
BUSINESS_HOURS: dict[int, tuple[str, str]] = {
    0: ("09:00", "19:00"),
    1: ("09:00", "19:00"),
    2: ("09:00", "19:00"),
    3: ("09:00", "19:00"),
    4: ("09:00", "19:00"),
}

# 予約候補を出す日数（営業日換算ではなくカレンダー上の日数）。
LOOKAHEAD_DAYS = 14

# 候補スロットの粒度（分）。
SLOT_STEP_MIN = 30

# 1日に表示する候補スロットの上限（多すぎると重いので絞る）。
MAX_SLOTS_PER_DAY = 14

# 予約可能な所要時間（分）。
DURATION_CHOICES_MIN = (30, 45, 60, 90)

# 「今から最低 N 分先しか取れない」バッファ。
MIN_LEAD_TIME_MIN = 90

# どの場所の予定なのか推定できなかったときの既定値。
# "online" にしておくと「物理移動は不要」と仮定するので穏当。
DEFAULT_LOCATION_KEY = "online"

# Distance Matrix API のキャッシュTTL（秒）。
TRAVEL_CACHE_TTL_SEC = 60 * 60 * 12

# Distance Matrix が呼べないときの保険として、固定値（分）も持っておく。
# 対称行列を想定して両方向に同じ値を使う。
FALLBACK_TRAVEL_MIN: dict[frozenset[str], int] = {
    frozenset({"bentencho", "umeda"}): 20,
    frozenset({"bentencho", "basecamp"}): 60,
    frozenset({"umeda", "basecamp"}): 50,
    frozenset({"bentencho"}): 0,
    frozenset({"umeda"}): 0,
    frozenset({"basecamp"}): 0,
}


def host_timezone() -> ZoneInfo:
    return ZoneInfo(os.environ.get("HOST_TIMEZONE", "Asia/Tokyo"))


def host_calendar_id() -> str:
    return os.environ.get("HOST_CALENDAR_ID", "primary")


def host_email() -> str:
    return os.environ.get("HOST_EMAIL", "")


def host_display_name() -> str:
    return os.environ.get("HOST_DISPLAY_NAME", "ご担当者")


def public_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def admin_token() -> str:
    return os.environ.get("ADMIN_TOKEN", "")


def maps_api_key() -> str:
    return os.environ.get("GOOGLE_MAPS_API_KEY", "")
