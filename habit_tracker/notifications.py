import logging
import os
from datetime import timedelta

import httpx

from .database import get_conn, get_setting
from .stats import today_jst

logger = logging.getLogger(__name__)


def _checks_on(d) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM checks WHERE check_date = ?",
            (d.isoformat(),),
        ).fetchone()
        return row["c"] if row else 0


def _habits_existed_on(d) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM habits WHERE archived = 0 AND created_at <= ?",
            (d.isoformat(),),
        ).fetchone()
        return row["c"] if row else 0


def send_email(to_addr: str, subject: str, html: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY")
    from_addr = os.environ.get("RESEND_FROM", "Habit Tracker <onboarding@resend.dev>")
    if not api_key:
        logger.warning("RESEND_API_KEY is not set; skipping email send")
        return False

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_addr,
                "to": [to_addr],
                "subject": subject,
                "html": html,
            },
            timeout=15.0,
        )
        if resp.status_code >= 300:
            logger.error("Resend API error %s: %s", resp.status_code, resp.text)
            return False
        return True
    except Exception as e:
        logger.exception("Failed to send notification email: %s", e)
        return False


def check_and_notify_missed() -> dict:
    """Check if user forgot to record yesterday's habits and send email.

    Returns a status dict for logging/inspection.
    """
    enabled = get_setting("notification_enabled", "1") == "1"
    if not enabled:
        return {"sent": False, "reason": "notifications disabled"}

    email = get_setting("notification_email")
    if not email:
        return {"sent": False, "reason": "no email configured"}

    yesterday = today_jst() - timedelta(days=1)

    if _habits_existed_on(yesterday) == 0:
        return {"sent": False, "reason": "no habits existed yesterday"}

    if _checks_on(yesterday) > 0:
        return {"sent": False, "reason": "checks already recorded for yesterday"}

    subject = f"【習慣チェック】昨日（{yesterday.strftime('%Y/%m/%d')}）の記入忘れ"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h2 style="color: #1f2937;">昨日のタスク記入忘れのお知らせ</h2>
      <p style="color: #374151; line-height: 1.7;">
        昨日（<strong>{yesterday.strftime('%Y年%m月%d日')}</strong>）の習慣タスクが記録されていません。
      </p>
      <p style="color: #374151; line-height: 1.7;">
        遅れて記入する場合は、アプリにアクセスして昨日の日付を選択してチェックしてください。
      </p>
      <p style="color: #6b7280; font-size: 14px; margin-top: 32px;">
        ※ この通知は習慣化アプリより自動配信されています。<br/>
        通知の停止はアプリ内設定から変更できます。
      </p>
    </div>
    """

    ok = send_email(email, subject, html)
    return {"sent": ok, "to": email, "date": yesterday.isoformat()}
