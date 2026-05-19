"""スケジューラ機能の FastAPI ルーター。

エンドポイント:
  GET  /admin?token=...           管理画面（OAuth認可状態と認可開始リンク）
  GET  /oauth2/start              OAuth 認可開始（管理者専用）
  GET  /oauth2/callback           OAuth 認可コールバック
  GET  /book                      予約フォーム（場所と所要時間を選ぶ）
  POST /book/slots                空きスロット一覧（HTML部分置換）
  POST /book/confirm              予約確定
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from scheduler import google_auth
from scheduler.availability import find_available_slots, validate_slot_still_open
from scheduler.calendar_service import create_event, extract_meet_link
from scheduler.config import (
    DURATION_CHOICES_MIN,
    LOCATIONS,
    admin_token,
    host_display_name,
    host_email,
    host_timezone,
    location_choices,
    public_base_url,
)

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# OAuth 認可フローの state を短期保持（in-memory）。
_pending_oauth_states: set[str] = set()


def _require_admin(token: str | None) -> None:
    expected = admin_token()
    if not expected or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="管理者トークンが必要です。")


def _render(template_name: str, request: Request, **context):
    base = {
        "host_name": host_display_name(),
        "locations": location_choices(),
        "durations": DURATION_CHOICES_MIN,
    }
    base.update(context)
    return templates.TemplateResponse(request, template_name, base)


# --- 管理画面 ----------------------------------------------------------------


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, token: Annotated[str | None, Query()] = None):
    _require_admin(token)
    authorized = google_auth.is_authorized()
    return _render(
        "admin.html",
        request,
        authorized=authorized,
        admin_token_value=token,
        booking_url=f"{public_base_url()}/book",
    )


@router.get("/oauth2/start")
def oauth2_start(token: Annotated[str | None, Query()] = None):
    _require_admin(token)
    try:
        flow = google_auth.build_flow()
    except google_auth.OAuthNotConfigured as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    _pending_oauth_states.add(state)
    return RedirectResponse(auth_url)


@router.get("/oauth2/callback", response_class=HTMLResponse)
def oauth2_callback(request: Request):
    state = request.query_params.get("state")
    if not state or state not in _pending_oauth_states:
        raise HTTPException(status_code=400, detail="OAuth state が不正です。やり直してください。")
    _pending_oauth_states.discard(state)

    try:
        flow = google_auth.build_flow(state=state)
        flow.fetch_token(authorization_response=str(request.url))
        google_auth.save_credentials(flow.credentials)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth 取得に失敗: {exc}") from exc

    return _render("oauth_done.html", request)


# --- 予約フォーム ------------------------------------------------------------


@router.get("/book", response_class=HTMLResponse)
def book_form(request: Request):
    return _render(
        "book.html",
        request,
        slots_by_day=None,
        chosen_location=None,
        chosen_duration=None,
    )


@router.post("/book/slots", response_class=HTMLResponse)
def book_slots(
    request: Request,
    location: Annotated[str, Form()],
    duration: Annotated[int, Form()],
):
    if location not in LOCATIONS:
        raise HTTPException(status_code=400, detail="場所の指定が不正です。")
    if duration not in DURATION_CHOICES_MIN:
        raise HTTPException(status_code=400, detail="所要時間の指定が不正です。")

    target = LOCATIONS[location]
    try:
        slots = find_available_slots(target, duration)
    except google_auth.OAuthNotAuthorized:
        return _render(
            "book.html",
            request,
            slots_by_day=None,
            chosen_location=target,
            chosen_duration=duration,
            error="ホスト側のGoogleカレンダー連携がまだ完了していません。管理者にお問い合わせください。",
        )
    except google_auth.OAuthNotConfigured as exc:
        return _render(
            "book.html",
            request,
            slots_by_day=None,
            chosen_location=target,
            chosen_duration=duration,
            error=str(exc),
        )

    return _render(
        "book.html",
        request,
        slots_by_day=slots,
        chosen_location=target,
        chosen_duration=duration,
    )


@router.post("/book/confirm_form", response_class=HTMLResponse)
def book_confirm_form(
    request: Request,
    location: Annotated[str, Form()],
    duration: Annotated[int, Form()],
    slot_start: Annotated[str, Form()],
):
    if location not in LOCATIONS:
        raise HTTPException(status_code=400, detail="場所の指定が不正です。")
    if duration not in DURATION_CHOICES_MIN:
        raise HTTPException(status_code=400, detail="所要時間の指定が不正です。")
    target = LOCATIONS[location]
    tz = host_timezone()
    try:
        start = datetime.fromisoformat(slot_start)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"開始時刻のフォーマットが不正です: {exc}") from exc
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    end = start + timedelta(minutes=duration)
    return _render(
        "confirm_form.html",
        request,
        chosen_location=target,
        chosen_duration=duration,
        slot_start=start,
        slot_end=end,
    )


@router.post("/book/confirm", response_class=HTMLResponse)
def book_confirm(
    request: Request,
    location: Annotated[str, Form()],
    duration: Annotated[int, Form()],
    slot_start: Annotated[str, Form()],
    guest_name: Annotated[str, Form()],
    guest_email: Annotated[str, Form()] = "",
    purpose: Annotated[str, Form()] = "",
):
    if location not in LOCATIONS:
        raise HTTPException(status_code=400, detail="場所の指定が不正です。")
    if duration not in DURATION_CHOICES_MIN:
        raise HTTPException(status_code=400, detail="所要時間の指定が不正です。")
    if not guest_name.strip():
        raise HTTPException(status_code=400, detail="お名前を入力してください。")

    target = LOCATIONS[location]
    tz = host_timezone()
    try:
        start = datetime.fromisoformat(slot_start)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"開始時刻のフォーマットが不正です: {exc}") from exc
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    end = start + timedelta(minutes=duration)

    ok, reason = validate_slot_still_open(start=start, end=end, target_location=target)
    if not ok:
        return _render(
            "book.html",
            request,
            slots_by_day=None,
            chosen_location=target,
            chosen_duration=duration,
            error=reason,
        )

    try:
        event = create_event(
            start=start,
            end=end,
            location=target,
            guest_name=guest_name.strip(),
            guest_email=guest_email.strip() or None,
            purpose=purpose.strip(),
            host_email=host_email(),
        )
    except google_auth.OAuthNotAuthorized:
        raise HTTPException(status_code=503, detail="ホスト側のGoogleカレンダー連携が切れています。")

    return _render(
        "confirmed.html",
        request,
        event_summary=event.get("summary"),
        event_start=start,
        event_end=end,
        target_location=target,
        meet_link=extract_meet_link(event) if target.is_online else None,
        html_link=event.get("htmlLink"),
        guest_name=guest_name.strip(),
    )
