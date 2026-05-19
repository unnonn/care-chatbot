"""Google OAuth2 のフロー & トークン永続化。

1人運用前提なので、認可済みの refresh token を1つだけ
ファイル（GOOGLE_OAUTH_TOKEN_PATH）に保存して使い回す。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from scheduler.config import public_base_url

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

REDIRECT_PATH = "/oauth2/callback"

_lock = threading.Lock()


class OAuthNotConfigured(RuntimeError):
    pass


class OAuthNotAuthorized(RuntimeError):
    pass


def _client_config() -> dict[str, Any]:
    raw = os.environ.get("GOOGLE_OAUTH_CLIENT_JSON", "").strip()
    if not raw:
        raise OAuthNotConfigured(
            "GOOGLE_OAUTH_CLIENT_JSON が設定されていません。"
            "Google Cloud Console で発行した OAuth クライアント JSON を環境変数に貼り付けてください。"
        )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OAuthNotConfigured(f"GOOGLE_OAUTH_CLIENT_JSON が JSON として読めません: {exc}") from exc


def _token_path() -> str:
    return os.environ.get("GOOGLE_OAUTH_TOKEN_PATH", "./google_token.json")


def redirect_uri() -> str:
    return f"{public_base_url()}{REDIRECT_PATH}"


def build_flow(state: str | None = None) -> Flow:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = redirect_uri()
    return flow


def save_credentials(creds: Credentials) -> None:
    path = _token_path()
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    with _lock:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)


def load_credentials() -> Credentials:
    """保存済みトークンを読み込み、必要ならリフレッシュする。"""
    path = _token_path()
    if not os.path.exists(path):
        raise OAuthNotAuthorized(
            "Google カレンダーがまだ連携されていません。管理者ページから初回認可を行ってください。"
        )

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
    )

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
            save_credentials(creds)
        else:
            raise OAuthNotAuthorized("リフレッシュトークンが無効です。再認可してください。")

    return creds


def is_authorized() -> bool:
    try:
        load_credentials()
        return True
    except (OAuthNotAuthorized, OAuthNotConfigured):
        return False
