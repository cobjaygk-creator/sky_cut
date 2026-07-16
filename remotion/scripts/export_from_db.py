"""
Export BlogShorts props from local SQLite (no API server required).

Usage (from repo root or remotion/):
  python remotion/scripts/export_from_db.py --clip-id 3 --user-id 1
  python remotion/scripts/export_from_db.py --clip-id 3 --email you@example.com
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

# Ensure sqlite:///./new_cut.db resolves to backend/new_cut.db
import os  # noqa: E402

os.chdir(BACKEND_ROOT)

from app.db.database import get_connection  # noqa: E402
from app.services.remotion_props_service import build_blog_shorts_props  # noqa: E402


def resolve_user_id(conn, user_id: int | None, email: str | None) -> int:
    if user_id is not None:
        return user_id
    if email:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        if row is None:
            raise SystemExit(f"No user with email {email!r}")
        return int(row["id"])
    row = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
    if row is None:
        raise SystemExit("No users in database.")
    return int(row["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Remotion BlogShorts props from new_cut.db")
    parser.add_argument("--clip-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--email", type=str, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default: remotion/out/props-{clip-id}.json)",
    )
    parser.add_argument("--no-materialize", action="store_true")
    args = parser.parse_args()

    out_path = args.out or (REPO_ROOT / "remotion" / "out" / f"props-{args.clip_id}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gen = get_connection()
    conn = next(gen)
    try:
        uid = resolve_user_id(conn, args.user_id, args.email)
        props = build_blog_shorts_props(
            conn,
            uid,
            args.clip_id,
            materialize=not args.no_materialize,
        )
    finally:
        next(gen, None)

    out_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Boards: {len(props['boards'])}  title={props.get('title')!r}")
    print()
    print("Studio:  npm run studio")
    print("         (load props via CLI render, or paste into Studio Props)")
    print(f'Render:  npx remotion render BlogShorts out/blog-clip-{args.clip_id}.mp4 --props="{out_path.as_posix()}"')


if __name__ == "__main__":
    main()
