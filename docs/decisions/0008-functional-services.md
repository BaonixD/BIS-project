# 0008. Функциональные сервисы и тонкие роутеры

Статус: принято владельцем 3 ноября 2026 года. Заменяет слой `repository` из [BACKEND_PLAN.md](../../BACKEND_PLAN.md) §4–5.

## Контекст

Бизнес-логика была написана классами (`AuthService`, `RideService`, `DispatchService`, …) с отдельными классами `*Repository` и `*Queries`. Роутеры собирали сервисы фабриками `get_*_service`, иногда вызывали несколько сервисов подряд и несли длинные docstring со списками ошибок. Владелец выбрал функциональный стиль с внедрением зависимостей через FastAPI.

## Решение

**Сервисы — функции модуля.** `service.py` содержит `async def` бизнес-операции: первым аргументом `db: AsyncSession`, затем данные операции, затем keyword-only зависимости (`clock`, `hasher`, `limiter`, `policy`, `settings`, `routing`). Классов-сервисов нет.

```python
async def login(
    db: AsyncSession, username: str, password: str, *,
    clock: Clock, hasher: PasswordHasher, limiter: LoginAttemptLimiter,
    replaces_token: str | None = None,
) -> IssuedSession: ...
```

**SQL — в сервисном модуле.** Слои `repository.py` и `queries.py` удалены. Запросы — короткие функции рядом с бизнес-операциями: приватные (`_get_active_session`) или публичные, если их зовёт другой модуль (`users.service.get_user_by_username`). Большой модуль делится по сценариям, а не по слоям: `rides/service.py`, `rides/dispatch.py`, `rides/lifecycle.py`.

**Транзакции не меняются.** Одна команда — один `async with db.begin()` в бизнес-функции; чтение — `read_transaction(db)`; функции-запросы не начинают и не коммитят транзакцию; внешний HTTP и Argon2 — вне транзакции; фоновые задачи открывают собственную сессию. Порядок блокировок ADR 0006/0007 сохраняется.

**Зависимости — `dependencies.py` модуля.** Там `Annotated`-зависимости на объекты из `app.state` и настройки (`PasswordHasherDep`, `LoginLimiterDep`, `RoutingProviderDep`, `DispatchPolicyDep`, `PaymentSettingsDep`), `CurrentUser`, `require_roles`. Сессия — `DbSession` из `database/session.py`. Фабрик сервисов нет.

**Роутер тонкий.** Один `router.py` на модуль. Эндпоинт берёт зависимости, вызывает одну функцию сервиса и превращает результат в схему ответа; кроме этого — только HTTP: cookie, заголовки, статус. Условий бизнес-логики в роутере нет. Импорт: `from taxi_service.modules.rides import service`.

**Комментарии короткие.** У эндпоинтов нет docstring: контракт ошибок описан `responses=error_responses(...)` в OpenAPI и в [api-handoff.md](../api-handoff.md). У функций docstring нет, если имени и типов достаточно; иначе — одна строка. Комментарий — одна строка о неочевидной причине.

**Классы остаются там, где они не бизнес-логика:** ORM-модели, Pydantic-схемы, перечисления, неизменяемые dataclass-результаты, исключения и инфраструктура с состоянием (`PasswordHasher`, `LoginAttemptLimiter`, `OpenRouteServiceClient`, `DispatchLoop`, `SystemClock`, middleware, настройки).

## Последствия

- Поведение API, коды ошибок, схема БД и миграции не меняются; новых миграций нет. API-, e2e- и миграционные тесты остаются как есть; тесты удалённых классов переписаны на функции без ослабления проверок.
- Описание эндпоинтов в OpenAPI становится короче; подробности — в api-handoff.md.
- Правило «репозитории не коммитят» становится «функции-запросы не начинают транзакцию».
