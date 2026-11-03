# FINAL: backend MVP Mini Taxi Service — передача на ревью Astra

Дата: 3 ноября 2026 года. Исполнение: главная сессия Claude Opus 5.5 и подагенты Opus 5.5 (исполнители с правилами `bis-implementer`, ревьюеры с правилами `bis-reviewer`). Это самопроверка Claude; итоговая приёмка Astra ещё не состоялась.

## Ветка и состояние

- Ветка: `integration/backend-mvp` (локальная; push, PR и слияние в `main` не выполнялись — нужна отдельная команда владельца).
- Основа пакета: `main` `98e3883`. Итоговый SHA — последний коммит ветки, в которой лежит этот файл (`git log -1 integration/backend-mvp`).
- Alembic head: `272671ab4753` (единственная).
- Задачи T00–T10 интегрированы; T11 (Google) отложена. Очередь и SHA каждой задачи — [docs/TASKS.md](../TASKS.md), отчёты — [T00](T00.md) · [T01](T01.md) · [T02](T02.md) · [T03](T03.md) · [T04](T04.md) · [T05](T05.md) · [T06](T06.md) · [T07](T07.md) · [T08](T08.md) · [T09](T09.md) · [T10](T10.md).

## Запуск

Полные команды — [README](../../README.md); устройство — [architecture.md](../architecture.md); контракт для React — [api-handoff.md](../api-handoff.md).

```bash
uv sync --locked
cp .env.example .env                 # DATABASE_URL, SESSION_COOKIE_SECURE=false для локального HTTP
uv run alembic upgrade head
ADMIN_PASSWORD=... uv run python scripts/create_admin.py --username admin
DEMO_PASSWORD=... uv run python scripts/seed.py       # демо-пассажиры и водители в Алматы
uv run uvicorn --factory taxi_service.main:create_app --port 8000
```

Проверки: `uv run python scripts/lint.py`, `uv run mypy src/taxi_service tests scripts`, `uv run pytest`.

## Итоговые проверки (главная сессия, integration после всех merge)

| Проверка | Результат |
| --- | --- |
| `uv sync --locked` | OK |
| `uv run python scripts/lint.py` | ruff check passed, 248 files formatted |
| `uv run mypy src/taxi_service tests scripts` | no issues in 237 files |
| `uv run pytest` | **1774 passed** (unit, integration на файловой SQLite, API, migrations, e2e) |
| `alembic upgrade head` / `check` / `heads` на одноразовой БД | `272671ab4753`, no new operations, одна head |
| `create_admin.py`, `seed.py` дважды | созданы; повтор без дубликатов |
| uvicorn `--factory` | `/health/live` ok, `/health/ready` ready, OpenAPI 30 путей / 33 операции; процесс остановлен |
| `scripts/routing_smoke.py` | `external_pending` (нет ключа), код 2 |
| Чистая копия (T10 B1) | clone → sync → migrate → admin → seed ×2 → serve → login → quote 503 без ключа → stop |

## Что реализовано

- Основа: FastAPI-монолит, единый конверт ошибок, `X-Request-ID`, JSON-логи, health, typed settings, `Clock`.
- БД: SQLite (ADR 0001), BEGIN IMMEDIATE для записи, отдельный путь только для чтения, Alembic с проверками миграций и сверкой частичных индексов.
- Вход: username/password (Argon2id), серверные сессии в HttpOnly cookie, CSRF, Origin, CORS, ограничение попыток, `create_admin`.
- Водители: профиль, машина, допуск admin, online, координаты, поиск кандидатов (haversine ≤ 5 км, свежесть 60 с).
- Маршрут и цена: адаптер openrouteservice (общий срок 10 с, предсказуемые ошибки), тариф `edu-v1` в KZT, `POST /geo/route`.
- Поездка: quote на 5 минут, идемпотентное создание (`Idempotency-Key`), назначение ближайшего водителя с предложением на 30 с и бюджетом поиска 180 с, фоновый цикл с восстановлением после перезапуска, команды arrive/start/complete/cancel/release, история событий, карточка водителя.
- Оплата: cash по умолчанию, Kaspi по ссылке владельца с ручным подтверждением admin, аудит, «Я оплатил» ≠ подтверждено.
- История и admin-чтение с пагинацией без N+1; демо-seed; E2E и тесты восстановления; документация.

## Отклонения от плана Astra (решения владельца и главной сессии)

- **SQLite вместо PostgreSQL/PostGIS и без Docker** — решение владельца ([ADR 0001](../decisions/0001-sqlite-without-docker.md)). Ближайший водитель — haversine; блокировки `FOR UPDATE`/`FOR NO KEY UPDATE` описаны для переносимости, на SQLite запись сериализует BEGIN IMMEDIATE.
- **Частые коммиты от Git-идентичности владельца** — по его просьбе; ветки сливались `merge --no-ff`.
- **Параллельность выше плана** (до 3–4 исполнителей) по просьбе владельца: из T04, T07, T08 и T10 выделены независимые части; T09 и seed шли параллельно T06. Владение файлами и миграциями разведено заранее, конфликты слияния — только в README, `.env.example`, `api/v1.py`.
- Профили `bis-implementer`/`bis-reviewer` не загружались сессией (репозиторий склонирован после старта); подагенты получали их правила из файлов. Отдельный ревьюер работал для T00–T03, T04 A, T05, T06, T07 B, T08 B; T04 B, T07 A, T08 A, T09, T10 — самопроверка главной сессии (отмечено в отчётах).
- Пакет seed — `src/taxi_service/seeds/`, а не корневой `seeds/`: без правки `sys.path`.

## Внешние зависимости (external_pending)

| Что | Состояние | Что нужно от владельца |
| --- | --- | --- |
| Реальный дорожный маршрут по Алматы | адаптер и ошибки проверены на контролируемых ответах; реальный запрос не выполнялся | бесплатный ключ openrouteservice в `ROUTING_API_KEY` (локальный `.env`), затем `uv run python scripts/routing_smoke.py` |
| Kaspi по ссылке | ссылка владельца получена, лежит только в локальном `.env`, проходит валидацию; оплата по ней не выполнялась | при демонстрации — ручная сверка в Kaspi POS и подтверждение admin |
| Google-вход (T11) | deferred | отдельная команда и client credentials |
| Роли участников команды, дата защиты, требования преподавателя | не сообщены | — |

## Решения, которые стоит подтвердить владельцу

1. Повтор `POST /rides` с тем же `Idempotency-Key` после ошибки `409 active_ride_exists` может создать поездку, если прежняя к тому времени завершилась (записывается только успешное создание; ADR 0005).
2. Бюджет поиска 180 с проверяется перед новым предложением: последнее предложение живёт полные 30 с, назначение возможно до ~210 с (ADR 0006).
3. Смена метода оплаты Kaspi → cash сбрасывает заявление `reported` в `unpaid` (ADR 0004).
4. Водитель на активной поездке не может уйти offline или менять профиль (409 `driver_on_active_ride`); причины отмены и release — свободный текст.

## Ограничения

- PostgreSQL не проверялся: переносимость подтверждена только компиляцией DDL/SQL; гоночные тесты на SQLite доказывают сериализацию, а не пересечение транзакций. Известное ограничение для PostgreSQL READ COMMITTED: проверка «водитель на поездке» может не увидеть незакоммиченный accept.
- Ограничитель входа и состояние — в памяти одного процесса; запуск в несколько воркеров не поддерживается.
- Нет очистки старых сессий, quote, записей идемпотентности, предложений и событий; нет WebSocket — клиенты опрашивают API.
- Интерфейс (React) не входит в этот этап; для защиты он нужен отдельно ([api-handoff.md](../api-handoff.md)).
- Отложенные мелочи ревью: CHECK формата телефона в `driver_profiles` и отсутствия пробелов в номере машины (нужна миграция).

## Как передать дальше

```text
Claude выполнил пакет. Проверь integration/backend-mvp и
docs/reports/FINAL.md, выполни итоговое ревью и проверь готовность бэкенда.
```

Ветка локальная: для ревью на другой машине нужна команда владельца на push.
