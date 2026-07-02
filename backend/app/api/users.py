import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db.database import get_connection
from app.db.models import User
from app.db.schemas import UserResponse
from app.services.user_service import get_user_by_id

router = APIRouter(tags=["users"])
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    conn: sqlite3.Connection = Depends(get_connection),
) -> User:
    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")
    user = get_user_by_id(conn, int(subject))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


@router.get("/me", response_model=UserResponse)
def read_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=current_user.id, email=current_user.email, created_at=current_user.created_at)
