from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from trialsync.api.errors import ApplicationError
from trialsync.db.models import User
from trialsync.db.session import get_db_session
from trialsync.security import decode_access_token

bearer = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: SessionDep,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApplicationError(
            code="AUTHENTICATION_REQUIRED", message="Sign in is required.", status_code=401
        )
    user_id = decode_access_token(
        credentials.credentials, request.app.state.settings.require_auth_secret()
    )
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise ApplicationError(
            code="INVALID_TOKEN", message="The access token is invalid or expired.", status_code=401
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
