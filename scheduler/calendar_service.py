"""Google Calendar API ラッパ。

- 指定期間の予定を取得し、各予定にどの拠点で行われるかをタグ付け。
- 新規予定の作成（オンラインなら Google Meet も同時生成）。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from googleapiclient.discovery import build

from scheduler.config import (
    DEFAULT_LOCATION_KEY,
    LOCATIONS,
    Location,
    host_calendar_id,
    host_timezone,
)
from scheduler.google_auth import load_credentials


@dataclass
class CalendarEvent:
    start: datetime
    end: datetime
    location: Location
    summary: str
    raw_location: str


def _service():
    creds = load_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _classify_location(location_text: str | None) -> Location:
    if not location_text:
        return LOCATIONS[DEFAULT_LOCATION_KEY]
    text = location_text.lower()
    for loc in LOCATIONS.values():
        for kw in loc.keywords:
            if kw.lower() in text:
                return loc
    return LOCATIONS[DEFAULT_LOCATION_KEY]


def list_events(start: datetime, end: datetime) -> list[CalendarEvent]:
    """[start, end) と重なる予定を、場所推定付きで返す。"""
    svc = _service()
    response = (
        svc.events()
        .list(
            calendarId=host_calendar_id(),
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
        )
        .execute()
    )

    tz = host_timezone()
    events: list[CalendarEvent] = []
    for item in response.get("items", []):
        # 招待で「辞退」したものは無視。
        if _self_response(item) == "declined":
            continue
        # 透過予定（空き扱い）の予定はブロックしない。
        if item.get("transparency") == "transparent":
            continue

        start_at = _parse_event_time(item.get("start"), tz)
        end_at = _parse_event_time(item.get("end"), tz)
        if start_at is None or end_at is None:
            continue

        raw_loc = item.get("location") or _conference_hint(item)
        loc = _classify_location(raw_loc)
        events.append(
            CalendarEvent(
                start=start_at,
                end=end_at,
                location=loc,
                summary=item.get("summary", ""),
                raw_location=raw_loc or "",
            )
        )
    return events


def _conference_hint(item: dict[str, Any]) -> str | None:
    cd = item.get("conferenceData") or {}
    for entry in cd.get("entryPoints") or []:
        uri = entry.get("uri")
        if uri:
            return uri
    return None


def _self_response(item: dict[str, Any]) -> str | None:
    for att in item.get("attendees") or []:
        if att.get("self"):
            return att.get("responseStatus")
    return None


def _parse_event_time(payload: dict[str, Any] | None, tz) -> datetime | None:
    if not payload:
        return None
    if "dateTime" in payload:
        return datetime.fromisoformat(payload["dateTime"].replace("Z", "+00:00")).astimezone(tz)
    if "date" in payload:
        # 終日予定は丸一日ブロック扱い。
        return datetime.fromisoformat(payload["date"]).replace(tzinfo=tz)
    return None


def create_event(
    *,
    start: datetime,
    end: datetime,
    location: Location,
    guest_name: str,
    guest_email: str | None,
    purpose: str,
    host_email: str,
) -> dict[str, Any]:
    svc = _service()

    summary = f"面談: {guest_name} 様"
    description_lines = [
        f"用件: {purpose or '(記載なし)'}",
        f"形式: {location.label}",
    ]
    if guest_email:
        description_lines.append(f"ゲスト連絡先: {guest_email}")

    body: dict[str, Any] = {
        "summary": summary,
        "description": "\n".join(description_lines),
        "start": {"dateTime": start.isoformat(), "timeZone": str(host_timezone())},
        "end": {"dateTime": end.isoformat(), "timeZone": str(host_timezone())},
        "reminders": {"useDefault": True},
    }

    if not location.is_online:
        body["location"] = location.address

    attendees: list[dict[str, Any]] = []
    if guest_email:
        attendees.append({"email": guest_email, "displayName": guest_name})
    if host_email:
        attendees.append({"email": host_email, "organizer": True, "responseStatus": "accepted"})
    if attendees:
        body["attendees"] = attendees

    insert_kwargs: dict[str, Any] = {
        "calendarId": host_calendar_id(),
        "body": body,
        "sendUpdates": "all" if guest_email else "none",
    }

    if location.is_online:
        body["conferenceData"] = {
            "createRequest": {
                "requestId": uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
        insert_kwargs["conferenceDataVersion"] = 1

    return svc.events().insert(**insert_kwargs).execute()


def extract_meet_link(event: dict[str, Any]) -> str | None:
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    cd = event.get("conferenceData") or {}
    for entry in cd.get("entryPoints") or []:
        if entry.get("entryPointType") == "video":
            return entry.get("uri")
    return None
