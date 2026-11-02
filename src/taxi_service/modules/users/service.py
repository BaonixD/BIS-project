from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taxi_service.core.clock import Clock
from taxi_service.database.session import read_transaction
from taxi_service.modules.auth.passwords import PasswordHasher
from taxi_service.modules.users.exceptions import UsernameTakenError
from taxi_service.modules.users.models import User, UserRole
from taxi_service.modules.users.repository import UserRepository, normalize_username


class UserService:
    def __init__(self, session: AsyncSession, clock: Clock, hasher: PasswordHasher) -> None:
        self._session = session
        self._clock = clock
        self._hasher = hasher
        self._users = UserRepository(session)

    async def create_user(self, *, username: str, password: str, role: UserRole) -> User:
        """Create an account; ``UsernameTakenError`` if the name exists in any case.

        Callers validate the username and password format. The password is
        hashed before the transaction, so the write lock is held only for the
        INSERT; the unique constraint decides concurrent registrations.
        """
        user = User(
            username=username,
            username_normalized=normalize_username(username),
            password_hash=await self._hasher.hash(password),
            role=role,
            created_at=self._clock.now(),
        )
        try:
            async with self._session.begin():
                await self._users.add(user)
        except IntegrityError as error:
            if await self._username_exists(username):
                raise UsernameTakenError from error
            raise
        return user

    async def _username_exists(self, username: str) -> bool:
        async with read_transaction(self._session):
            return await self._users.get_by_username(username) is not None
