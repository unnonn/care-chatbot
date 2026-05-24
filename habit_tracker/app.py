import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .database import get_conn, get_setting, init_db, set_setting
from .notifications import check_and_notify_missed
from .stats import JST, habit_stats, overall_stats, today_jst

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

scheduler = AsyncIOScheduler(timezone=JST)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Daily check at 10:00 JST for missed yesterday entries
    scheduler.add_job(
        check_and_notify_missed,
        CronTrigger(hour=10, minute=0, timezone=JST),
        id="daily_missed_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Habit tracker started, scheduler running")
    yield
    scheduler.shutdown()


app = FastAPI(title="Habit Tracker", lifespan=lifespan)


# ---------- Models ----------

class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    task_type: str = Field(pattern="^(morning|evening)$")


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    task_type: str | None = Field(default=None, pattern="^(morning|evening)$")


class ReorderItem(BaseModel):
    id: int
    sort_order: int
    task_type: str = Field(pattern="^(morning|evening)$")


class ReorderBody(BaseModel):
    items: list[ReorderItem]


class CheckIn(BaseModel):
    habit_id: int
    check_date: date


class SettingsIn(BaseModel):
    notification_email: str | None = None
    notification_enabled: bool | None = None


# ---------- Static / Frontend ----------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/stats")
def stats_page():
    return FileResponse(STATIC_DIR / "stats.html")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Habits ----------

def _row_to_habit(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "task_type": r["task_type"],
        "sort_order": r["sort_order"],
        "created_at": r["created_at"],
        "archived": bool(r["archived"]),
    }


@app.get("/api/habits")
def list_habits():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM habits WHERE archived = 0 ORDER BY task_type, sort_order, id"
        ).fetchall()
        return [_row_to_habit(r) for r in rows]


@app.post("/api/habits")
def create_habit(body: HabitIn):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next FROM habits "
            "WHERE task_type = ? AND archived = 0",
            (body.task_type,),
        ).fetchone()
        next_order = row["next"]
        cur = conn.execute(
            "INSERT INTO habits (name, task_type, sort_order, created_at) "
            "VALUES (?, ?, ?, ?)",
            (body.name.strip(), body.task_type, next_order, today_jst().isoformat()),
        )
        habit_id = cur.lastrowid
        new = conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
        return _row_to_habit(new)


@app.put("/api/habits/{habit_id}")
def update_habit(habit_id: int, body: HabitUpdate):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Habit not found")

        name = body.name.strip() if body.name else existing["name"]
        task_type = body.task_type or existing["task_type"]

        sort_order = existing["sort_order"]
        if task_type != existing["task_type"]:
            row = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next FROM habits "
                "WHERE task_type = ? AND archived = 0",
                (task_type,),
            ).fetchone()
            sort_order = row["next"]

        conn.execute(
            "UPDATE habits SET name = ?, task_type = ?, sort_order = ? WHERE id = ?",
            (name, task_type, sort_order, habit_id),
        )
        updated = conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
        return _row_to_habit(updated)


@app.delete("/api/habits/{habit_id}")
def delete_habit(habit_id: int):
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM habits WHERE id = ?", (habit_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Habit not found")
        conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
        return {"deleted": habit_id}


@app.post("/api/habits/reorder")
def reorder_habits(body: ReorderBody):
    with get_conn() as conn:
        for item in body.items:
            conn.execute(
                "UPDATE habits SET sort_order = ?, task_type = ? WHERE id = ?",
                (item.sort_order, item.task_type, item.id),
            )
    return {"ok": True}


# ---------- Checks ----------

@app.get("/api/checks")
def list_checks(start: date, end: date):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT habit_id, check_date FROM checks WHERE check_date BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [{"habit_id": r["habit_id"], "check_date": r["check_date"]} for r in rows]


@app.post("/api/checks/toggle")
def toggle_check(body: CheckIn):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM checks WHERE habit_id = ? AND check_date = ?",
            (body.habit_id, body.check_date.isoformat()),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM checks WHERE id = ?", (existing["id"],))
            return {"habit_id": body.habit_id, "check_date": body.check_date.isoformat(), "checked": False}
        else:
            conn.execute(
                "INSERT INTO checks (habit_id, check_date) VALUES (?, ?)",
                (body.habit_id, body.check_date.isoformat()),
            )
            return {"habit_id": body.habit_id, "check_date": body.check_date.isoformat(), "checked": True}


# ---------- Stats ----------

@app.get("/api/stats/habit/{habit_id}")
def get_habit_stats(habit_id: int, start: date | None = None, end: date | None = None):
    result = habit_stats(habit_id, start, end)
    if not result:
        raise HTTPException(404, "Habit not found")
    return result


@app.get("/api/stats/overall")
def get_overall_stats(start: date | None = None, end: date | None = None):
    return overall_stats(start, end)


# ---------- Settings ----------

@app.get("/api/settings")
def get_settings():
    return {
        "notification_email": get_setting("notification_email", ""),
        "notification_enabled": get_setting("notification_enabled", "1") == "1",
    }


@app.put("/api/settings")
def update_settings(body: SettingsIn):
    if body.notification_email is not None:
        set_setting("notification_email", body.notification_email.strip())
    if body.notification_enabled is not None:
        set_setting("notification_enabled", "1" if body.notification_enabled else "0")
    return get_settings()


@app.post("/api/notifications/test")
def test_notification():
    """Manually trigger the missed-check notification (for testing)."""
    return check_and_notify_missed()
