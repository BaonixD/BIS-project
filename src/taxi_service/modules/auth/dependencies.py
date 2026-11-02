from typing import Annotated

from fastapi import Depends, Request

from taxi_service.core.clock import ClockDep
from taxi_service.database.session import SessionDep
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.users.service import UserService


def get_password_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


def get_user_service(
    session: SessionDep, clock: ClockDep, hasher: PasswordHasherDep
) -> UserService:
    return UserService(session, clock, hasher)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
