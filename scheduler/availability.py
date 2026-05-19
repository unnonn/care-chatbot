"""Google カレンダーの既存予定を見て、希望場所と整合する空きスロットを返す。

要点:
- 営業時間内のグリッド（30分刻み）を全部出してから、
  既存予定とぶつかるもの・移動時間が確保できないものを順に除外。
- 「前の予定の場所 → 候補場所」「候補場所 → 次の予定の場所」の
  どちらの移動も成立しない場合は候補から落とす。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from scheduler.calendar_service import CalendarEvent, list_events
from scheduler.config import (
    BUSINESS_HOURS,
    LOCATIONS,
    LOOKAHEAD_DAYS,
    MAX_SLOTS_PER_DAY,
    MIN_LEAD_TIME_MIN,
    SLOT_STEP_MIN,
    Location,
    host_timezone,
)
from scheduler.travel import travel_minutes


@dataclass
class Slot:
    start: datetime
    end: datetime

    @property
    def date_key(self) -> str:
        return self.start.strftime("%Y-%m-%d")

    @property
    def time_label(self) -> str:
        return f"{self.start.strftime('%H:%M')}–{self.end.strftime('%H:%M')}"

    @property
    def iso_start(self) -> str:
        return self.start.isoformat()


def _business_window(day: datetime) -> tuple[datetime, datetime] | None:
    hours = BUSINESS_HOURS.get(day.weekday())
    if not hours:
        return None
    tz = host_timezone()
    start_h, start_m = (int(x) for x in hours[0].split(":"))
    end_h, end_m = (int(x) for x in hours[1].split(":"))
    start = day.replace(hour=start_h, minute=start_m, second=0, microsecond=0, tzinfo=tz)
    end = day.replace(hour=end_h, minute=end_m, second=0, microsecond=0, tzinfo=tz)
    return start, end


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _previous_and_next(
    events: list[CalendarEvent], slot_start: datetime, slot_end: datetime
) -> tuple[CalendarEvent | None, CalendarEvent | None]:
    prev_evt: CalendarEvent | None = None
    next_evt: CalendarEvent | None = None
    for ev in events:
        if ev.end <= slot_start:
            if prev_evt is None or ev.end > prev_evt.end:
                prev_evt = ev
        elif ev.start >= slot_end:
            if next_evt is None or ev.start < next_evt.start:
                next_evt = ev
    return prev_evt, next_evt


def find_available_slots(target_location: Location, duration_min: int) -> dict[str, list[Slot]]:
    """date(YYYY-MM-DD) -> 空きスロット一覧 を返す。"""
    tz = host_timezone()
    now = datetime.now(tz)
    horizon_start = now
    horizon_end = (now + timedelta(days=LOOKAHEAD_DAYS)).replace(
        hour=23, minute=59, second=0, microsecond=0
    )

    events = list_events(horizon_start, horizon_end)
    earliest_allowed = now + timedelta(minutes=MIN_LEAD_TIME_MIN)

    result: dict[str, list[Slot]] = {}
    duration = timedelta(minutes=duration_min)
    step = timedelta(minutes=SLOT_STEP_MIN)

    for day_offset in range(LOOKAHEAD_DAYS + 1):
        day = (now + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        window = _business_window(day)
        if not window:
            continue
        win_start, win_end = window

        cursor = win_start
        day_slots: list[Slot] = []
        while cursor + duration <= win_end:
            slot_start = cursor
            slot_end = cursor + duration
            cursor = cursor + step

            if slot_start < earliest_allowed:
                continue

            # 既存予定との衝突
            collision = any(_overlaps(slot_start, slot_end, ev.start, ev.end) for ev in events)
            if collision:
                continue

            prev_evt, next_evt = _previous_and_next(events, slot_start, slot_end)

            if prev_evt is not None:
                need = timedelta(minutes=travel_minutes(prev_evt.location, target_location))
                if slot_start - prev_evt.end < need:
                    continue
            if next_evt is not None:
                need = timedelta(minutes=travel_minutes(target_location, next_evt.location))
                if next_evt.start - slot_end < need:
                    continue

            day_slots.append(Slot(start=slot_start, end=slot_end))
            if len(day_slots) >= MAX_SLOTS_PER_DAY:
                break

        if day_slots:
            result[day_slots[0].date_key] = day_slots

    return result


def validate_slot_still_open(
    *, start: datetime, end: datetime, target_location: Location
) -> tuple[bool, str | None]:
    """確定直前の二重ブロック。"""
    events = list_events(start - timedelta(hours=12), end + timedelta(hours=12))
    for ev in events:
        if _overlaps(start, end, ev.start, ev.end):
            return False, "選んだ時間帯にすでに予定が入っています。別の枠を選んでください。"
    prev_evt, next_evt = _previous_and_next(events, start, end)
    if prev_evt is not None:
        need = timedelta(minutes=travel_minutes(prev_evt.location, target_location))
        if start - prev_evt.end < need:
            return False, "直前の予定からの移動時間が足りなくなりました。別の枠をご検討ください。"
    if next_evt is not None:
        need = timedelta(minutes=travel_minutes(target_location, next_evt.location))
        if next_evt.start - end < need:
            return False, "直後の予定への移動時間が足りなくなりました。別の枠をご検討ください。"
    return True, None
