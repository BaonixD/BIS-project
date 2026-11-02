from taxi_service.core.config import Settings


class PasswordHasher:
    def __init__(self, *, time_cost: int, memory_kib: int, parallelism: int) -> None:
        self.time_cost = time_cost
        self.memory_kib = memory_kib
        self.parallelism = parallelism

    @classmethod
    def from_settings(cls, settings: Settings) -> "PasswordHasher":
        return cls(
            time_cost=settings.password_hash_time_cost,
            memory_kib=settings.password_hash_memory_kib,
            parallelism=settings.password_hash_parallelism,
        )

    async def hash(self, password: str) -> str:
        raise NotImplementedError

    async def verify(self, password_hash: str | None, password: str) -> bool:
        raise NotImplementedError
