import sqlite3
from datetime import datetime, timezone

from fastapi import HTTPException, status

PLAN_POLICIES = {
    "free": {
        "id": "free",
        "name": "Free",
        "monthly_video_limit": 3,
        "max_video_minutes": 10,
        "description": "For local MVP testing and light personal use.",
    },
    "lite": {
        "id": "lite",
        "name": "Lite",
        "monthly_video_limit": 30,
        "max_video_minutes": 30,
        "description": "For regular creators processing short and medium videos.",
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "monthly_video_limit": 150,
        "max_video_minutes": 120,
        "description": "For heavy creator workflows with long source videos.",
    },
}


def current_usage_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def plan_policy(plan: str | None) -> dict:
    normalized = (plan or "free").lower()
    return PLAN_POLICIES.get(normalized, PLAN_POLICIES["free"])


def list_plan_policies() -> list[dict]:
    return list(PLAN_POLICIES.values())


def _fetch_user_usage_row(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT id, plan, monthly_usage, usage_limit, usage_month
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return row


def sync_user_usage_policy(conn: sqlite3.Connection, user_id: int) -> dict:
    row = _fetch_user_usage_row(conn, user_id)
    policy = plan_policy(row["plan"])
    month = current_usage_month()
    stored_month = row["usage_month"]
    monthly_usage = int(row["monthly_usage"])

    if stored_month != month:
        monthly_usage = 0
        stored_month = month

    if row["plan"] != policy["id"] or int(row["usage_limit"]) != policy["monthly_video_limit"] or row["usage_month"] != stored_month or int(row["monthly_usage"]) != monthly_usage:
        conn.execute(
            """
            UPDATE users
            SET plan = ?, monthly_usage = ?, usage_limit = ?, usage_month = ?
            WHERE id = ?
            """,
            (policy["id"], monthly_usage, policy["monthly_video_limit"], stored_month, user_id),
        )
        conn.commit()

    return {
        "plan": policy["id"],
        "plan_name": policy["name"],
        "monthly_usage": monthly_usage,
        "usage_limit": policy["monthly_video_limit"],
        "remaining": max(policy["monthly_video_limit"] - monthly_usage, 0),
        "usage_month": stored_month,
        "max_video_minutes": policy["max_video_minutes"],
    }


def assert_can_analyze_video(conn: sqlite3.Connection, user_id: int, duration_seconds: float) -> dict:
    usage = sync_user_usage_policy(conn, user_id)
    if usage["monthly_usage"] >= usage["usage_limit"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Monthly analysis limit reached for {usage['plan_name']} plan ({usage['usage_limit']} videos/month).",
        )

    duration_minutes = duration_seconds / 60
    if duration_minutes > usage["max_video_minutes"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Video is {duration_minutes:.1f} minutes. {usage['plan_name']} plan supports up to {usage['max_video_minutes']} minutes per video.",
        )
    return usage


def increment_monthly_usage(conn: sqlite3.Connection, user_id: int) -> dict:
    usage = sync_user_usage_policy(conn, user_id)
    next_usage = min(usage["monthly_usage"] + 1, usage["usage_limit"])
    conn.execute(
        """
        UPDATE users
        SET monthly_usage = ?, usage_limit = ?, usage_month = ?
        WHERE id = ?
        """,
        (next_usage, usage["usage_limit"], usage["usage_month"], user_id),
    )
    conn.commit()
    usage["monthly_usage"] = next_usage
    usage["remaining"] = max(usage["usage_limit"] - next_usage, 0)
    return usage
