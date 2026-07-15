from __future__ import annotations

from fastapi import APIRouter, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import User
from trialsync.schemas import LoginRequest, TokenResponse, UserCreate, UserRead
from trialsync.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, request: Request, session: SessionDep) -> TokenResponse:
    user = User(
        email=str(payload.email).lower(),
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="EMAIL_ALREADY_REGISTERED",
            message="An account with this email already exists.",
            status_code=409,
            field="email",
        ) from exception
    await session.refresh(user)
    settings = request.app.state.settings
    token = create_access_token(
        user.id, settings.require_auth_secret(), settings.access_token_minutes
    )
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, session: SessionDep) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise ApplicationError(
            code="INVALID_CREDENTIALS", message="Email or password is incorrect.", status_code=401
        )
    settings = request.app.state.settings
    token = create_access_token(
        user.id, settings.require_auth_secret(), settings.access_token_minutes
    )
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
