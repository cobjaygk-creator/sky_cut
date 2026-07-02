import sqlite3

from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password
from app.db.models import User


def _row_to_user(row: sqlite3.Row) -> User:
    return User(id=row["id"], email=row["email"], created_at=row["created_at"])


def get_user_by_email(conn: sqlite3.Connection, email: str) -> User | None:
    row = conn.execute("SELECT id, email, created_at FROM users WHERE email = ?", (email.lower(),)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def create_user(conn: sqlite3.Connection, email: str, password: str) -> User:
    normalized_email = email.lower()
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (normalized_email, hash_password(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.") from exc

    user = get_user_by_id(conn, int(cursor.lastrowid))
    if user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User creation failed.")
    return user


def authenticate_user(conn: sqlite3.Connection, email: str, password: str) -> User:
    row = conn.execute(
        "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
        (email.lower(),),
    ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return _row_to_user(row)
