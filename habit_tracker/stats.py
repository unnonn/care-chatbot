from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .database import get_conn

JST = ZoneInfo("Asia/Tokyo")


def today_jst() -> date:
    return datetime.now(JST).date()


def _count_between(conn, habit_id: int, start: date, end: date) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM checks WHERE habit_id = ? AND check_date BETWEEN ? AND ?",
        (habit_id, start.isoformat(), end.isoformat()),
    ).fetchone()
    return row["c"] if row else 0


def _start_of_week(d: date) -> date:
    # Week starts on Monday
    return d - timedelta(days=d.weekday())


def _pct_change(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _longest_streak(dates: list[date]) -> tuple[int, date | None, date | None]:
    if not dates:
        return 0, None, None
    dates = sorted(set(dates))
    best = 1
    best_start = dates[0]
    best_end = dates[0]
    cur = 1
    cur_start = dates[0]
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            cur += 1
        else:
            cur = 1
            cur_start = dates[i]
        if cur > best:
            best = cur
            best_start = cur_start
            best_end = dates[i]
    return best, best_start, best_end


def habit_stats(habit_id: int, period_start: date | None = None, period_end: date | None = None) -> dict:
    today = today_jst()
    with get_conn() as conn:
        habit = conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
        if not habit:
            return {}

        created_at = date.fromisoformat(habit["created_at"])

        rows = conn.execute(
            "SELECT check_date FROM checks WHERE habit_id = ? ORDER BY check_date",
            (habit_id,),
        ).fetchall()
        all_dates = [date.fromisoformat(r["check_date"]) for r in rows]

        cumulative = len(all_dates)
        last_check = max(all_dates) if all_dates else None

        # This year / last year
        year_start = date(today.year, 1, 1)
        this_year = _count_between(conn, habit_id, year_start, today)

        # This month / last month
        month_start = date(today.year, today.month, 1)
        if today.month == 1:
            last_month_start = date(today.year - 1, 12, 1)
            last_month_end = date(today.year - 1, 12, 31)
        else:
            last_month_start = date(today.year, today.month - 1, 1)
            last_month_end = month_start - timedelta(days=1)
        this_month = _count_between(conn, habit_id, month_start, today)
        last_month = _count_between(conn, habit_id, last_month_start, last_month_end)

        # This week / last week (Mon-Sun)
        week_start = _start_of_week(today)
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        this_week = _count_between(conn, habit_id, week_start, today)
        last_week = _count_between(conn, habit_id, last_week_start, last_week_end)

        # Period total
        if period_start and period_end:
            period_total = _count_between(conn, habit_id, period_start, period_end)
        else:
            period_total = this_week

        # Longest streak
        streak, streak_start, streak_end = _longest_streak(all_dates)

        days_elapsed = (today - created_at).days

        return {
            "id": habit["id"],
            "name": habit["name"],
            "task_type": habit["task_type"],
            "created_at": habit["created_at"],
            "period_total": period_total,
            "cumulative": cumulative,
            "this_year": this_year,
            "this_month": this_month,
            "last_month": last_month,
            "this_month_change": _pct_change(this_month, last_month),
            "this_week": this_week,
            "last_week": last_week,
            "this_week_change": _pct_change(this_week, last_week),
            "last_check_date": last_check.isoformat() if last_check else None,
            "longest_streak": streak,
            "longest_streak_start": streak_start.isoformat() if streak_start else None,
            "longest_streak_end": streak_end.isoformat() if streak_end else None,
            "days_elapsed": days_elapsed,
        }


def overall_stats(period_start: date | None = None, period_end: date | None = None) -> dict:
    today = today_jst()
    with get_conn() as conn:
        habits = conn.execute(
            "SELECT id, name, task_type, created_at FROM habits WHERE archived = 0"
        ).fetchall()

        habit_ids = [h["id"] for h in habits]
        if not habit_ids:
            return {
                "period_total": 0,
                "cumulative": 0,
                "this_year": 0,
                "this_month": 0,
                "last_month": 0,
                "this_month_change": None,
                "this_week": 0,
                "last_week": 0,
                "this_week_change": None,
                "last_check_date": None,
                "days_elapsed": 0,
                "per_habit": [],
                "monthly_breakdown": [],
            }

        placeholders = ",".join("?" * len(habit_ids))

        def count(start: date, end: date) -> int:
            row = conn.execute(
                f"SELECT COUNT(*) AS c FROM checks WHERE habit_id IN ({placeholders}) "
                f"AND check_date BETWEEN ? AND ?",
                (*habit_ids, start.isoformat(), end.isoformat()),
            ).fetchone()
            return row["c"] if row else 0

        cumulative_row = conn.execute(
            f"SELECT COUNT(*) AS c FROM checks WHERE habit_id IN ({placeholders})",
            habit_ids,
        ).fetchone()
        cumulative = cumulative_row["c"] if cumulative_row else 0

        last_row = conn.execute(
            f"SELECT MAX(check_date) AS d FROM checks WHERE habit_id IN ({placeholders})",
            habit_ids,
        ).fetchone()
        last_check = last_row["d"] if last_row and last_row["d"] else None

        year_start = date(today.year, 1, 1)
        this_year = count(year_start, today)

        month_start = date(today.year, today.month, 1)
        if today.month == 1:
            last_month_start = date(today.year - 1, 12, 1)
            last_month_end = date(today.year - 1, 12, 31)
        else:
            last_month_start = date(today.year, today.month - 1, 1)
            last_month_end = month_start - timedelta(days=1)
        this_month = count(month_start, today)
        last_month = count(last_month_start, last_month_end)

        week_start = _start_of_week(today)
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        this_week = count(week_start, today)
        last_week = count(last_week_start, last_week_end)

        if period_start and period_end:
            period_total = count(period_start, period_end)
        else:
            period_total = this_week

        earliest = min(date.fromisoformat(h["created_at"]) for h in habits)
        days_elapsed = (today - earliest).days

        # Per-habit summary
        per_habit = []
        for h in habits:
            per_habit.append({
                "id": h["id"],
                "name": h["name"],
                "task_type": h["task_type"],
                "this_month": _count_between(conn, h["id"], month_start, today),
                "this_week": _count_between(conn, h["id"], week_start, today),
                "cumulative": conn.execute(
                    "SELECT COUNT(*) AS c FROM checks WHERE habit_id = ?",
                    (h["id"],),
                ).fetchone()["c"],
            })

        # Monthly breakdown for last 12 months
        monthly = []
        for i in range(11, -1, -1):
            y, m = today.year, today.month - i
            while m <= 0:
                y -= 1
                m += 12
            ms = date(y, m, 1)
            if m == 12:
                me = date(y, 12, 31)
            else:
                me = date(y, m + 1, 1) - timedelta(days=1)
            if me > today:
                me = today
            monthly.append({
                "year": y,
                "month": m,
                "count": count(ms, me),
            })

        return {
            "period_total": period_total,
            "cumulative": cumulative,
            "this_year": this_year,
            "this_month": this_month,
            "last_month": last_month,
            "this_month_change": _pct_change(this_month, last_month),
            "this_week": this_week,
            "last_week": last_week,
            "this_week_change": _pct_change(this_week, last_week),
            "last_check_date": last_check,
            "days_elapsed": days_elapsed,
            "per_habit": per_habit,
            "monthly_breakdown": monthly,
        }
