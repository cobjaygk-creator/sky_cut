import sqlite3

from fastapi import APIRouter, Depends

from app.core.security import create_access_token
from app.db.database import get_connection
from app.db.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.user_service import authenticate_user, create_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, conn: sqlite3.Connection = Depends(get_connection)) -> UserResponse:
    user = create_user(conn, payload.email, payload.password)
    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, conn: sqlite3.Connection = Depends(get_connection)) -> TokenResponse:
    user = authenticate_user(conn, payload.email, payload.password)
    return TokenResponse(access_token=create_access_token(str(user.id)))
