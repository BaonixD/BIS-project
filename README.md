# BIS-project — Mini Taxi Service

Учебный проект по Basics of Information Systems. На текущем этапе подготовлены спецификация и пакет реализации бэкенда для Claude Code; реализованы основа приложения (T00: запуск API, health endpoints, единый формат ошибок, локальные проверки), слой БД (T01: SQLite, Alembic, тестовая изоляция) и вход (T02: регистрация, серверные сессии, CSRF, роли — раздел [Аутентификация](#аутентификация)). Профили, поездки и оплата появятся в следующих задачах.

Стек: Python, FastAPI, SQLAlchemy; на текущем этапе SQLite без Docker ([ADR 0001](docs/decisions/0001-sqlite-without-docker.md)). Локальный модульный монолит, без CI и микросервисов. React-интерфейс — следующий этап.

## Начать реализацию

Открыть репозиторий в Claude Code, выбрать Opus 5.5 и отправить стартовый промпт из [CLAUDE_START.md](CLAUDE_START.md).

| Документ | Назначение |
| --- | --- |
| [CLAUDE_START.md](CLAUDE_START.md) | Готовый промпт, запуск и продолжение сессии |
| [CLAUDE.md](CLAUDE.md) | Правила исполнителя, test-first и ограничения |
| [BACKEND_PLAN.md](BACKEND_PLAN.md) | Инженерный план и ответы опроса |
| [ORCHESTRATION.md](ORCHESTRATION.md) | Делегирование, ветки, ревью и интеграция |
| [docs/MVP_SPEC.md](docs/MVP_SPEC.md) | Контракты и рабочие допущения |
| [docs/TASKS.md](docs/TASKS.md) | T00–T10, зависимости, ветки и статусы; T11 отдельно |

Два профиля для Claude Code находятся в [.claude/agents](.claude/agents): изолированный исполнитель и независимый ревьюер. Главная сессия использует их правила при делегировании задач.

Реализация собирается в `integration/backend-mvp` для итогового ревью Astra. Команды установки, миграций, запуска и проверок — в разделе [Локальная разработка](#локальная-разработка); демо-данные — в разделе [Демонстрационные данные (seed)](#демонстрационные-данные-seed).

## Локальная разработка

Docker не используется ([ADR 0001](docs/decisions/0001-sqlite-without-docker.md)); всё запускается через `uv` из корня репозитория.

### Установка

Нужен [uv](https://docs.astral.sh/uv/) 0.12+ (проверено на 0.12.23). Версия Python (3.12) задана в `.python-version`; uv использует установленный интерпретатор или скачивает его сам.

```bash
uv sync --locked      # воспроизводит окружение .venv строго по uv.lock
cp .env.example .env  # локальные настройки; .env не коммитится
```

Пакет `taxi_service` (`src/`) устанавливается в `.venv` как часть проекта, без правки `sys.path`. Если активирован другой virtualenv, uv предупреждает `VIRTUAL_ENV ... will be ignored` и всё равно использует `.venv` проекта — это ожидаемо.

### Переменные окружения

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` или `CRITICAL`, без учёта регистра |
| `DATABASE_URL` | — (обязательна) | URL БД для приложения и Alembic; локально `sqlite+aiosqlite:///./taxi.db` |
| `KASPI_PAYMENT_URL` | пусто | Ссылка Kaspi владельца (хост `pay.kaspi.kz`); используется с T08, только в локальном `.env` |
| `ROUTING_API_KEY` | пусто | Ключ сервиса дорожных маршрутов; используется с T04, только в локальном `.env` |
| `SESSION_COOKIE_SECURE` | `true` | Флаг `Secure` cookie сессии; для локального `http://` — `false` (так в `.env.example`) |
| `CORS_ALLOWED_ORIGINS` | пусто | Origin браузерных клиентов через запятую, без `*`: CORS с credentials и проверка `Origin` у login/register |
| `PASSWORD_HASH_TIME_COST`, `PASSWORD_HASH_MEMORY_KIB`, `PASSWORD_HASH_PARALLELISM` | `3`, `65536`, `4` | Параметры Argon2id (RFC 9106 low-memory); уменьшаются только в тестах |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_ATTEMPT_WINDOW_SECONDS`, `LOGIN_LIMITER_MAX_KEYS` | `5`, `900`, `10000` | Ограничитель попыток входа на username |
| `OFFER_TTL_S`, `SEARCH_BUDGET_S` | `30`, `180` | Срок предложения водителю и общий бюджет поиска водителя, секунды |
| `DISPATCH_INTERVAL_S`, `DISPATCH_LOOP_ENABLED` | `1.0`, `true` | Интервал фонового цикла назначения; `false` выключает цикл (тесты) |
| `ADMIN_PASSWORD` | — | Только для `scripts/create_admin.py`; в `.env` не хранить |

Значения берутся из окружения процесса и из `.env` в текущем каталоге. Переменные последующих задач, которые приложение ещё не читает, игнорируются. Файлы `*.db`, `*.db-wal`, `*.db-shm` не попадают в Git.

### База данных и миграции

Локальная БД — файл SQLite ([ADR 0001](docs/decisions/0001-sqlite-without-docker.md)). В `sqlite+aiosqlite:///./taxi.db` путь относителен текущего каталога: команды запускаются из корня репозитория, файл — `./taxi.db` (рядом с ним при работе появляются `taxi.db-wal` и `taxi.db-shm`). Абсолютный путь пишется с четырьмя слешами: `sqlite+aiosqlite:////abs/path/taxi.db`.

Схема создаётся и обновляется только миграциями Alembic, отдельной командой до запуска API:

```bash
uv run alembic upgrade head   # создать/обновить схему; повторный запуск ничего не меняет
uv run alembic check          # модели и схема БД совпадают (нет операций для autogenerate)
uv run alembic current        # ревизия БД;  uv run alembic heads — ожидаемая (одна)
```

Alembic берёт URL из `DATABASE_URL` (окружение или `.env`); в `alembic.ini` URL не хранится. Чтобы проверить миграции на одноразовой БД, а не на рабочей, задайте URL явно: `DATABASE_URL=sqlite+aiosqlite:///./scratch-test.db uv run alembic upgrade head`.

Соединения SQLite открываются с `foreign_keys=ON`, WAL и `busy_timeout=5000` (подробности — `src/taxi_service/database/sqlite.py`). У сессий отключён autobegin: запрос вне явной транзакции вызывает ошибку. Есть два пути:

| Путь | Код | SQLite |
| --- | --- | --- |
| Запись, а также чтение, от которого зависит запись | `async with session.begin():` | `BEGIN IMMEDIATE`: пишущие транзакции выполняются по очереди |
| Только чтение | `async with read_transaction(session):` (`taxi_service.database.session`); без сессии — `read_connection(engine)` | `BEGIN DEFERRED` + `PRAGMA query_only`: не ждёт писателей, любая запись падает с ошибкой |

Правило: роутер или auth-зависимость — короткий `read_transaction`; сервис — один `async with session.begin()` на операцию; внутри транзакции никогда не ждать внешний HTTP (маршруты) и другой медленный ввод-вывод. `SessionDep` сам ничего не открывает и не коммитит. Опция выполнения `isolation_level` (включая `AUTOCOMMIT`) с этой схемой не поддерживается и отклоняется.

Миграции работают с отключённой на время проверкой внешних ключей (пересоздание таблицы в batch-режиме иначе каскадно удалило бы связанные строки) и перед commit выполняют `PRAGMA foreign_key_check`; при нарушении вся ревизия откатывается.

Новая модель: класс от `taxi_service.database.base.Base` (время — `UtcDateTime`), импорт её модуля в `src/taxi_service/database/metadata.py`, затем `uv run alembic revision --autogenerate -m "..."`, ручная проверка ревизии, `upgrade head` и `check` на одноразовой БД. История ревизий линейная, с одной head; первая ревизия `baseline` пустая.

Ограничение: путь к `alembic.ini` и `alembic/` вычисляется от расположения исходников (`taxi_service/database/migrations.py`, `parents[3]` — корень репозитория). Это работает при запуске из репозитория (editable-установка `uv sync`); из собранного wheel без репозитория readiness и `alembic_config()` каталог миграций не найдут.

### Резервная копия и восстановление локальной БД

Делайте копию перед потенциально разрушительными изменениями (новые миграции, ручные правки). Каталог `backups/` создаётся вручную; файлы `*.db` в Git не попадают.

Копия при остановленном приложении — просто файл. После корректной остановки содержимое WAL уже перенесено в основной файл; если `taxi.db-wal` непустой, скопируйте его вместе с `taxi.db`:

```bash
mkdir -p backups
cp taxi.db "backups/taxi-$(date +%Y%m%d-%H%M%S).db"
```

Согласованная копия без остановки приложения — встроенной командой SQLite (`sqlite3` есть в macOS):

```bash
sqlite3 taxi.db ".backup 'backups/taxi-$(date +%Y%m%d-%H%M%S).db'"
```

Восстановление — только при остановленном приложении:

```bash
rm -f taxi.db-wal taxi.db-shm             # служебные файлы WAL текущей БД
cp backups/taxi-YYYYMMDD-HHMMSS.db taxi.db
sqlite3 taxi.db "PRAGMA integrity_check"  # ожидается: ok
uv run alembic upgrade head               # если копия старше текущих миграций
```

### Запуск API

```bash
uv run alembic upgrade head

uv run uvicorn --factory taxi_service.main:create_app --port 8000
# для разработки: добавить --reload
```

- `GET /health/live` — `200 {"status": "ok"}`, процесс отвечает.
- `GET /health/ready` — `200 {"status": "ready"}`, только если БД отвечает на `SELECT 1` и её ревизия Alembic совпадает с head; иначе `503` с кодом `database_unavailable` (БД недоступна, файла SQLite нет или проверка не уложилась в 2 с) или `database_not_migrated` (нужно `alembic upgrade head`). Проверка идёт по пути чтения и не ждёт пишущих транзакций; отсутствующий файл не создаётся. URL БД в ответ не попадает.
- `GET /docs` — Swagger UI, `GET /openapi.json` — схема.

Миграции и seed при запуске не выполняются; это отдельные команды. Engine создаётся в lifespan и закрывается при остановке.

### Аутентификация

Серверные сессии по username/password, решение — [ADR 0003](docs/decisions/0003-auth-sessions-csrf.md). Маршруты под `/api/v1/auth`:

| Маршрут | Что делает | Ошибки |
| --- | --- | --- |
| `POST /register` | `{username, password, role}` → `201` пользователь без пароля; `role` — `passenger` или `driver` | `422` (формат, `role=admin`), `409 username_taken`, `403 origin_not_allowed` |
| `POST /login` | `{username, password}` → `200 {user, csrf_token, expires_at}` и cookie `taxi_session` | `401 invalid_credentials` (одинаково для неверного пароля и неизвестного username), `429 too_many_attempts`, `403 origin_not_allowed` |
| `GET /session` | текущий пользователь и `csrf_token` сессии | `401 not_authenticated` |
| `POST /logout` | отзывает сессию в БД и удаляет cookie → `204` | `401 not_authenticated`, `403 csrf_failed` |

- Username: 3–32 символа `[A-Za-z0-9_]`, уникален без учёта регистра; вход тоже без учёта регистра, написание сохраняется. Пароль: 10–128 символов, хранится только как Argon2id-хеш.
- Cookie `taxi_session`: `HttpOnly`, `SameSite=Lax`, `Path=/`, 7 дней. `Secure` управляется `SESSION_COOKIE_SECURE`: по умолчанию включён; для локального HTTP в `.env` — `false`, иначе браузер не вернёт cookie. В БД хранится только SHA-256 токена. Срок — 7 дней по серверным часам; новый вход в том же клиенте отзывает прежнюю сессию.
- CSRF: каждый `POST/PUT/PATCH/DELETE` с cookie сессии требует заголовок `X-CSRF-Token` со значением `csrf_token` именно этой сессии, иначе `403 csrf_failed`. GET его не требует.
- Origin: login и register с заголовком `Origin` принимаются, только если он есть в `CORS_ALLOWED_ORIGINS` или совпадает с origin самого API (Swagger UI); иначе `403 origin_not_allowed`. Запросы без `Origin` (curl, HTTPX) допускаются.
- Перебор: не больше 5 попыток входа на username за 15 минут (`429`, `details.retry_after_seconds`); счётчики в памяти процесса и сбрасываются при перезапуске.
- В коде: зависимости `CurrentUser` и `require_roles(...)` из `taxi_service.modules.auth.dependencies` (`401 not_authenticated`, `403 forbidden`).

Пример через curl с cookie jar (сервер запущен с `SESSION_COOKIE_SECURE=false`, т. к. адрес `http://`):

```bash
API=http://127.0.0.1:8000/api/v1
curl -s -X POST "$API/auth/register" -H 'Content-Type: application/json' \
  -d '{"username":"alice_01","password":"correct-horse-battery","role":"passenger"}'
curl -s -c jar.txt -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"alice_01","password":"correct-horse-battery"}'
CSRF=$(curl -s -b jar.txt "$API/auth/session" | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])')
curl -s -b jar.txt -c jar.txt -X POST "$API/auth/logout" -H "X-CSRF-Token: $CSRF"  # 204
curl -s -b jar.txt "$API/auth/session"                                               # 401
```

То же через HTTPX (клиент сам хранит cookie):

```python
import httpx

with httpx.Client(base_url="http://127.0.0.1:8000/api/v1") as client:
    credentials = {"username": "alice_01", "password": "correct-horse-battery"}
    client.post("/auth/register", json={**credentials, "role": "passenger"})
    client.post("/auth/login", json=credentials).raise_for_status()
    csrf = client.get("/auth/session").json()["csrf_token"]
    # любой изменяющий защищённый запрос — с заголовком X-CSRF-Token
    client.post("/auth/logout", headers={"X-CSRF-Token": csrf}).raise_for_status()
    assert client.get("/auth/session").status_code == 401
```

В Swagger UI (`/docs`): выполнить register и login (cookie сохранит браузер), затем скопировать `csrf_token` из `GET /auth/session` в **Authorize → CsrfToken**.

Администратор создаётся только локальной командой, не через API; постоянный пароль в репозиторий не попадает:

```bash
uv run python scripts/create_admin.py --username admin   # пароль спросит дважды (getpass)
ADMIN_PASSWORD='...' uv run python scripts/create_admin.py --username admin   # без запроса
```

Коды выхода: `0` — создан; `1` — username уже существует в любом регистре (ничего не меняется) либо БД отсутствует или не мигрирована; `2` — некорректные username или пароль.

### Ошибки, request_id и логи

Любой ответ с ошибкой, включая неизвестный маршрут (404), неверный метод (405), ошибку валидации (422) и непредвиденную ошибку (500), имеет формат из [MVP_SPEC §3](docs/MVP_SPEC.md#3-общий-контракт-api):

```json
{"error": {"code": "not_found", "message": "Not Found", "details": {}}, "request_id": "..."}
```

Для 422 `details.errors` содержит только `loc`, `msg`, `type` — без присланных значений. Ответ 500 не раскрывает текст исключения.

Каждый ответ содержит заголовок `X-Request-ID`. Клиентское значение сохраняется, если оно не длиннее 64 символов из `[A-Za-z0-9._-]`; иначе генерируется новое. Логи приложения (`taxi_service.*`) пишутся в stderr по одному JSON-объекту на строку с полем `request_id`.

### Проверки

```bash
uv run python scripts/lint.py        # ruff check + ruff format --check, файлы не меняет
uv run mypy src/taxi_service tests scripts   # strict
uv run pytest                        # unit, API, интеграция с БД и миграции; без внешних сервисов
```

Тесты не используют `DATABASE_URL` и `taxi.db`: переменная удаляется из окружения теста. Шаблонная БД один раз мигрируется через Alembic во временном каталоге pytest, каждый тест получает собственную копию файла (`tests/conftest.py`: фикстуры `database_url`, `engine`, `session_factory`, `settings`, `clock`, `app`, `client`, `empty_database_url`). Фикстура `settings` сохраняет безопасные значения по умолчанию и снижает только стоимость Argon2id; `clock` — `ManualClock`, время двигается через `clock.advance(...)` без ожидания; `client` работает с `https://testserver`, поэтому cookie с `Secure` возвращается. Общие помощники — пакет `tests/support` (импорт `support.*`): `support.auth.register_and_login(client, username, role=...)` регистрирует и входит, возвращая пользователя с `csrf_headers` для изменяющих запросов. Удалять и перезаписывать файлы БД фикстуры могут только внутри временного каталога pytest, независимо от имени файла (`taxi_service.database.safety`). `:memory:` не используется: конкурентным тестам нужны независимые соединения к одному файлу.

Явное исправление стиля — отдельными командами:

```bash
uv run ruff check --fix .
uv run ruff format .
```

CI и Git hooks не настраиваются; проверки запускаются локально.

## Продукт

Алматы, KZT. Вход по username/password. Поездка предлагается ближайшему доступному водителю; 30 секунд на ответ, затем следующий. Реальный дорожный маршрут, учебный расчёт цены, наличные и Kaspi по ссылке с ручным подтверждением. Google-вход — последующий этап.

Реальный запрос маршрута потребует API-ключа, Kaspi — ссылки владельца. Секреты и локальные `.env` в Git не добавляются.

## Маршруты

Дорожный маршрут строит openrouteservice Directions (`driving-car`), решение и контракт ошибок — [ADR 0002](docs/decisions/0002-routing-provider.md). Статус реальной проверки: **external_pending** — ключа пока нет, настоящий маршрут по Алматы не запрашивался.

### Ключ openrouteservice

1. Зарегистрироваться на [openrouteservice.org](https://openrouteservice.org/) (аккаунт HeiGIT) и в личном кабинете создать бесплатный ключ плана Standard. Платный план не подключается.
2. Записать ключ только в локальный `.env`: `ROUTING_API_KEY=...`. В `.env.example`, Git, логи и ответы API ключ не попадает. Ключ персональный, на клиенте (React, мобильное приложение) не используется.
3. Остальные `ROUTING_*` (базовый URL, таймауты, повторы, общий срок одного запроса — 10 с по умолчанию) необязательны; значения по умолчанию перечислены в `.env.example`.

Без ключа приложение запускается как обычно, а маршрут отвечает `503 routing_unavailable` без обращения к провайдеру; подставной маршрут не выдаётся.

### `POST /api/v1/geo/route`

Любая роль с сессией; как и любой изменяющий запрос, нужен заголовок `X-CSRF-Token`. Тело — две точки `{longitude, latitude}` (WGS 84), лишние поля запрещены:

```bash
curl -s -b jar.txt -X POST "$API/geo/route" -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d '{"origin":{"longitude":76.9572,"latitude":43.2389},"destination":{"longitude":76.9286,"latitude":43.2187}}'
```

Ответ `200` — нормализованный `RouteResult`; `route_geometry` — GeoJSON `LineString`, каждая позиция `[longitude, latitude]`. Цены в ответе нет: её считает quote поездки (T05).

```json
{"distance_m": 4121, "duration_s": 610,
 "route_geometry": {"type": "LineString", "coordinates": [[76.9572, 43.2389], [76.9286, 43.2187]]},
 "provider": "openrouteservice"}
```

| Код | Когда |
| --- | --- |
| `401 not_authenticated`, `403 csrf_failed` | нет сессии или CSRF-токена |
| `422 validation_error` | координаты вне диапазона, не числа, лишние поля |
| `422 route_points_identical` | origin и destination совпадают; провайдер не вызывается |
| `422 route_not_found` | провайдер не нашёл дорожного маршрута между точками |
| `503 routing_unavailable` | `ROUTING_API_KEY` не задан |
| `503 routing_provider_error` | сбой провайдера; `details.reason`: `timeout`, `connection_error`, `rate_limited`, `provider_unavailable`, `rejected`, `invalid_response` |

Запрос к провайдеру выполняется вне транзакции БД. В тестах провайдер подменяется через `create_app(settings, routing_provider=...)`; контролируемый `FakeRoutingProvider` — в `tests/support/routing.py`. Pytest к сети не обращается.

### Проверка реального маршрута

```bash
uv run python scripts/routing_smoke.py
```

Один реальный запрос по Алматы (Абая/Достык → Аль-Фараби) с ключом из окружения или `.env`. Коды выхода: `0` — маршрут получен, `1` — ошибка провайдера или неправдоподобная геометрия, `2` — `external_pending` (ключа нет, запрос не выполнялся). Pytest этот скрипт не запускает.

### Условия и атрибуция

Действуют [условия HeiGIT](https://account.heigit.org/info/tos) и лимиты бесплатного плана (по FAQ ORS — порядка 2000 запросов Directions в сутки и 40 в минуту; превышение — `429`/`403`, здесь это `routing_provider_error`). Маршруты строятся на данных OpenStreetMap (ODbL): интерфейс, показывающий маршрут, должен выводить атрибуцию, например «© openrouteservice.org by HeiGIT | Map data © OpenStreetMap contributors». Точный текст сверить с условиями при получении ключа.

## Водители и профили

Все маршруты — под `/api/v1`, с сессией; изменяющие запросы требуют `X-CSRF-Token` (см. «Аутентификация»). Идентификатора в путях `/me` нет: пользователь читает и меняет только себя. Лишние поля тела (`role`, `id`, `username`, `approval_status`, `online` и т. п.) и `null` вместо значения дают `422 validation_error`; пропущенное поле не меняется.

| Маршрут | Роль | Что делает |
| --- | --- | --- |
| `GET/PATCH /users/me` | любая | аккаунт и контакты: `display_name` (1–64 символа), `phone` |
| `GET/PATCH /drivers/me` | driver | `full_name`, `phone`, `license_number`, `vehicle` (`make`, `model`, `color`, `plate_number`, `year`) |
| `PUT /drivers/me/availability` | driver | `{"online": true\|false}` |
| `PUT /drivers/me/location` | driver | `{"longitude": ..., "latitude": ...}` |
| `GET /admin/drivers` | admin | список: `limit` (1–100, 20), `offset`, `approval_status=pending\|approved` |
| `POST /admin/drivers/{id}/approve` | admin | допуск водителя (`id` — id пользователя) |

Правила:

- Телефон хранится как `+` и цифры (`+7 701 123-45-67` → `+77011234567`); номер прав и госномер — заглавными без пробелов и `-` (`123 abc-02` → `123ABC02`). Госномер уникален среди всех водителей (`409 plate_number_taken`). Год выпуска — от 1980 до следующего года по часам сервера.
- У водителя одна машина; `vehicle` в PATCH заменяет все её поля. Ответ содержит `missing_fields` — чего не хватает для допуска.
- У водителя два телефона с разным назначением, они не синхронизируются. `phone` из `/drivers/me` (`driver_profiles.phone`) обязателен для допуска и показывается пассажиру в карточке водителя вместе с именем и машиной. `phone` из `/users/me` (`user_profiles.phone`) — необязательный контакт аккаунта, одинаковый для всех ролей; пассажиру водителя он не показывается.
- Новый водитель — `pending`. Admin допускает только полный профиль с машиной (`409 driver_profile_incomplete`, `details.missing_fields`); повторный допуск возвращает первый (`approved_at`, `approved_by` не меняются).
- Изменение `full_name`, `license_number` или машины у допущенного водителя возвращает его в `pending` и offline до нового допуска; телефон меняется без этого, повтор тех же значений ничего не сбрасывает.
- `online: true` — только допущенному водителю (`409 driver_not_approved`); offline разрешён всегда, кроме времени активной поездки. Это ограничение есть и в БД (CHECK).
- Во время своей поездки (`assigned/arrived/in_progress`) водитель не уходит offline и не меняет профиль и машину: `409 driver_on_active_ride` (раздел «Жизненный цикл поездки»); координаты обновляются как обычно.
- Координата одна текущая: `longitude` −180…180, `latitude` −90…90 включительно, числа JSON (не строки, не массив). Время `location_updated_at` ставит сервер; координаты пишет и не допущенный водитель.
- Список admin упорядочен по регистрации: `created_at DESC, id DESC`; водитель, ещё не заполнявший профиль, тоже в списке как `pending`.

Поиск кандидатов для назначения (T06): `taxi_service.modules.drivers.candidates.find_nearby_candidates(session, pickup, now=..., radius_m=5000, max_location_age_s=60, exclude_driver_ids=(), limit=10)` → `[Candidate(driver_id, distance_m)]`. Кандидат — допущенный, online, с машиной, координата не старше 60 с, расстояние haversine до pickup не больше 5 км (обе границы включительно). SQL отбирает строки в bounding box круга по индексу `(longitude, latitude)`, точное расстояние и порядок (расстояние, затем `driver_id`) считаются в Python. Функция работает в транзакции вызывающего сервиса.

В тестах: `support.drivers` — помощники через API (`registered_driver`, `approve`, `approved_driver`, `create_admin`, `complete_profile`), фикстура `driver_factory` — водители через сервисы без HTTP (`await driver_factory.driver("d1", location=Coordinates(...))`, `move`, `go_offline`; время координат — `clock`).

## Поездки: quote и создание

Все маршруты — под `/api/v1`, с сессией; POST требует `X-CSRF-Token`. Подробности и обоснование — [ADR 0005](docs/decisions/0005-quotes-idempotency.md).

| Маршрут | Роль | Что делает |
| --- | --- | --- |
| `POST /rides/quotes` | passenger | `{"pickup": {...}, "dropoff": {...}}` → `201`: `quote_id`, `route`, `amount_kzt`, `currency`, `tariff_version`, `expires_at` |
| `POST /rides` | passenger | `{"quote_id": "..."}` + заголовок `Idempotency-Key` → `201` поездка в `searching` без водителя |
| `GET /rides/{id}` | пассажир поездки, назначенный водитель, admin | поездка; участникам активной поездки — и карточка водителя `driver`; остальным `404 ride_not_found` |

Пример (после входа пассажиром, как в разделе «Аутентификация»: `$API`, `jar.txt`, `$CSRF`; нужен ключ маршрутизации):

```bash
QUOTE_ID=$(curl -s -b jar.txt -X POST "$API/rides/quotes" -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d '{"pickup":{"longitude":76.9572,"latitude":43.2389},"dropoff":{"longitude":76.9286,"latitude":43.2187}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["quote_id"])')
KEY=$(uuidgen)
curl -s -b jar.txt -X POST "$API/rides" -H "X-CSRF-Token: $CSRF" -H "Idempotency-Key: $KEY" \
  -H 'Content-Type: application/json' -d "{\"quote_id\":\"$QUOTE_ID\"}"   # 201, повтор — та же поездка
```

Правила:

- Цену считает сервер по дорожному маршруту (тариф `edu-v1`), quote действует 5 минут. Поездка копирует маршрут, сумму и `tariff_version` из quote; смена тарифа сохранённые quote и поездки не меняет. Сумма, статус или водитель в теле — `422 validation_error`.
- Маршрут запрашивается у провайдера вне транзакции БД; его ошибки (`503 routing_unavailable`, `503 routing_provider_error`, `422 route_not_found`, `422 route_points_identical`) возвращаются как есть, quote не создаётся.
- `Idempotency-Key`: 1–128 видимых ASCII-символов (подходит UUID), новый на каждый новый заказ. Повтор с тем же ключом и телом возвращает ту же поездку (`201`, заголовок `Idempotent-Replayed: true`); тот же ключ с другим `quote_id` — `409 idempotency_key_reused`. Нет ключа — `422 idempotency_key_required`, неверный формат — `422 idempotency_key_invalid`. Ключ действует для пользователя и операции; записи хранятся не меньше 24 часов (очистки пока нет).
- Ошибки создания: `404 quote_not_found` (нет или чужой), `409 quote_expired`, `409 quote_already_used`, `409 active_ride_exists` (у пассажира уже есть поездка `searching/assigned/arrived/in_progress`). Ограничения защищены и в БД (уникальный `quote_id`, частичные уникальные индексы активной поездки пассажира и принятой поездки водителя); одновременные запросы дают одну поездку и `409`, не `500`.
- Сразу после создания начинается поиск водителя (раздел «Назначение водителя»): ответ — `searching` с предложением ближайшему водителю или уже `no_driver`, если свободных водителей рядом нет. Повтор с тем же ключом поиск не перезапускает.

В тестах: `support.rides` — `request_quote`, `order_ride`, `ride_headers`, `ride_url`; фикстура `ride_factory` — пассажиры и поездки через сервисы без HTTP (`await ride_factory.searching_ride(pickup=Coordinates(...))`).

## История и администрирование

Только чтение, под `/api/v1`, с сессией. Списки — `{"items", "limit", "offset", "total"}`: `limit` 1–100 (по умолчанию 20), `offset` ≥ 0, порядок `created_at DESC, id DESC` (при одинаковом времени — по id); `offset` за концом даёт пустой `items` с верным `total`.

| Маршрут | Роль | Что возвращает |
| --- | --- | --- |
| `GET /rides` | passenger, driver | пассажир — свои поездки, включая активную; водитель — поездки, где он сейчас `driver_id` (отпущенная поездка из его истории уходит); admin — `403 forbidden` |
| `GET /admin/rides` | admin | все поездки; дополнительно фильтры `passenger_id`, `driver_id` (неизвестный id — пустая страница) |
| `GET /admin/users` | admin | `id`, `username`, `role`, `created_at`, `display_name` профиля (`null` без профиля); фильтр `role` |

Фильтры поездок сочетаются через И: `status` — один или несколько (`?status=completed&status=cancelled`); `created_from` — включительно, `created_to` — исключительно, то есть `[from, to)`. Время — ISO 8601 обязательно со смещением (`2026-11-03T09:00:00Z` или `+05:00`; в URL `+` кодируется как `%2B`), без смещения — `422 validation_error`; `created_from` позже `created_to` — `422 invalid_date_range`.

Элемент поездки (`RideSummary`): `id`, `status`, `passenger_id`, `driver_id`, `pickup`, `dropoff`, `distance_m`, `duration_s`, `amount_kzt`, `currency`, `created_at`, `updated_at`. Геометрии маршрута в списке нет — её отдаёт `GET /rides/{id}`. Пароли, хэши, токены сессии и CSRF, телефоны в ответы не попадают; изменить роль или статус через эти маршруты нельзя (`POST/PUT/PATCH/DELETE` — `404/405`).

Страница стоит одинаковое число SQL-запросов при любом размере: проверка сессии, строки страницы и `count` (`tests/api/test_list_statement_count.py`).

```bash
curl -s -b jar.txt "$API/rides?status=completed&limit=10"
curl -s -b jar.txt "$API/admin/users?role=driver"   # под admin
```

В тестах: `support.history` — `past_rides` (завершённые поездки со сдвигом `ManualClock`), `set_ride` (водитель и статус прямым UPDATE, пока нет dispatch), `get_page`, `count_statements`.

## Демонстрационные данные (seed)

Отдельная команда; приложение, lifespan и миграции её не вызывают. Нужна существующая SQLite-БД из `DATABASE_URL`, мигрированная до head:

```bash
uv run alembic upgrade head
uv run python scripts/seed.py                       # создать недостающие демо-аккаунты
uv run python scripts/seed.py --refresh-locations   # перед показом: свежие координаты, водители online
```

| Аккаунт | Роль | Что создаётся |
| --- | --- | --- |
| `demo_admin` | admin | допускает демо-водителей |
| `demo_passenger_1`, `demo_passenger_2` | passenger | `display_name` «Demo Passenger 1/2» |
| `demo_driver_1`…`demo_driver_3` | driver | полный профиль, машина `DEMO001KZ`…`DEMO003KZ`, допуск `demo_admin`, online |

Водители стоят в синтетических точках примерно в 300 м, 1,2 км и 2,5 км от демонстрационной точки посадки в центре Алматы (`latitude 43.2383, longitude 76.9457`; это не адреса реальных людей), поэтому поиск ближайшего водителя у этой точки находит их в этом порядке. Координата считается свежей 60 с: перед демонстрацией назначения выполните `--refresh-locations`.

- **Пароль** всех создаваемых демо-аккаунтов — `DEMO_PASSWORD` из окружения или локального `.env` (10–128 символов, как при регистрации); без неё команда спрашивает пароль дважды без эха (только в терминале). Пароль нужен, лишь когда есть что создавать; заданный `DEMO_PASSWORD` проверяется всегда. В выводе и Git его нет; постоянного демо-пароля в репозитории нет.
- **Повторный запуск** ничего не дублирует: ключ — username (без учёта регистра). Существующий демо-аккаунт пропускается без изменений (`skipped`), в том числе правки профиля, сделанные через API. `--refresh-locations` у существующих `demo_driver_*` меняет только координату (на демо-точку, время — серверное) и включает online; профиль и допуск не трогает и повторно не допускает: водитель, потерявший допуск после правки, остаётся offline с пояснением в выводе.
- **Безопасность окружения:** только файл SQLite (не PostgreSQL, не `:memory:`); отсутствующий файл не создаётся; немигрированная БД — ошибка. Ничего не удаляется и не очищается. Подтверждение `--yes` не требуется: команда только добавляет аккаунты с префиксом `demo_` и останавливается до любой записи, если демо-username уже занят аккаунтом другой роли или демо-номер машины — чужим водителем. Целевой файл печатается в первой строке вывода.
- **Коды выхода:** `0` — готово (сводка `created / skipped / refreshed`); `1` — окружение или БД (не SQLite-файл, нет файла, не мигрирована, конфликт с существующими данными); `2` — ввод (пароль вне 10–128 символов, повтор не совпал, нет терминала для запроса).
- Если запуск прервался посреди создания водителя, повторный запуск пропустит уже созданный аккаунт; проверьте его в `GET /api/v1/admin/drivers` и при необходимости завершите профиль и допуск через API.

Код: `scripts/seed.py` (CLI) и `src/taxi_service/seeds/demo.py` (данные и логика через `UserService`, `DriverService`, `DriverAdminService`). Пакет `seeds` лежит внутри `taxi_service`, а не в корне репозитория: так он импортируется из `scripts/` без правки `sys.path` и проверяется общей командой `uv run mypy src/taxi_service tests scripts`. Тесты — `tests/seeds/`; остальные тесты демо-seed не используют.

## Назначение водителя

Поиск — по одному водителю за раз, предложение действует 30 секунд, поиск — 180 секунд. Подробности и обоснование — [ADR 0006](docs/decisions/0006-dispatch.md).

| Маршрут | Роль | Что делает |
| --- | --- | --- |
| `GET /drivers/me/offers` | driver | открытые предложения (страница `items/limit/offset/total`, не больше одного): `ride_id`, `pickup`, `dropoff`, `distance_m`, `duration_s`, `amount_kzt`, `currency`, `expires_at` |
| `POST /ride-offers/{id}/accept` | адресат предложения | `200` поездка `assigned` с `driver_id`; повтор — тот же ответ |
| `POST /ride-offers/{id}/reject` | адресат предложения | `200` предложение `rejected`; поездка сразу предлагается следующему водителю |

Правила:

- Кандидат: допущен, online, есть машина, координата не старше 60 с, до pickup не дальше 5 км по прямой (haversine), нет поездки `assigned/arrived/in_progress` и нет другого открытого предложения. Ближайший — по расстоянию, при равенстве — меньший `driver_id`. В одном поиске водитель получает предложение по поездке не больше одного раза. После release начинается новый 180-секундный поиск: освободивший поездку водитель её больше не получает, а отказавшиеся раньше снова кандидаты.
- Предложение истекает при `now >= expires_at` (ровно 30 с — уже поздно): `409 offer_expired`, даже если фоновый цикл ещё не успел отметить; поездка переходит к следующему кандидату. Чужое или несуществующее предложение — `404 offer_not_found`; отклонённое/отозванное — `409 invalid_offer_transition`; у водителя уже есть активная поездка — `409 driver_busy`. POST требуют `X-CSRF-Token`.
- Нет кандидатов на шаге или прошло 180 с с начала поиска — поездка `no_driver`; пассажир может заказать снова. Последнее предложение, сделанное до конца бюджета, живёт полные 30 с.
- Водитель ушёл offline (или потерял допуск) — его открытое предложение `revoked`, цикл предлагает поездку следующему.
- Фоновый цикл работает внутри приложения (`DISPATCH_INTERVAL_S`, по умолчанию 1 с); Celery/Redis не нужны. Всё состояние в БД: после перезапуска первый проход приводит просроченные предложения в порядок, двойного назначения нет (частичные уникальные индексы: одно открытое предложение на поездку и на водителя; одна принятая активная поездка на водителя).
- Клиенты опрашивают `GET /drivers/me/offers` и `GET /rides/{id}`; WebSocket нет.

Пример ответа водителя (после входа водителем: `$API`, `jar.txt`, `$CSRF`):

```bash
OFFER_ID=$(curl -s -b jar.txt "$API/drivers/me/offers" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["items"][0]["id"])')
curl -s -b jar.txt -X POST "$API/ride-offers/$OFFER_ID/accept" -H "X-CSRF-Token: $CSRF"
```

В тестах цикл выключен (`DISPATCH_LOOP_ENABLED=false` в `tests/conftest.py`); фикстура `dispatcher` вызывает сервис напрямую (`process`, `process_due`, `accept`, `reject`, `offers`), время двигает `clock.advance(...)`. Фикстура `available_driver` — один свободный водитель у pickup по умолчанию, чтобы поездка из API оставалась `searching`.

## Жизненный цикл поездки

Команды назначенного водителя и пассажира, история переходов и защита от гонок. Подробности — [ADR 0007](docs/decisions/0007-ride-lifecycle.md).

```text
searching → assigned → arrived → in_progress → completed
searching → no_driver
searching / assigned / arrived → cancelled
assigned / arrived → searching  (release)
```

| Маршрут (POST, `X-CSRF-Token`) | Кто | Переход | Тело |
| --- | --- | --- | --- |
| `/rides/{id}/arrive` | назначенный водитель | assigned → arrived | — |
| `/rides/{id}/start` | назначенный водитель | arrived → in_progress | — |
| `/rides/{id}/complete` | назначенный водитель | in_progress → completed | — |
| `/rides/{id}/cancel` | пассажир поездки | searching / assigned / arrived → cancelled | необязательно `{"reason": "..."}` |
| `/rides/{id}/release` | назначенный водитель | assigned / arrived → searching | обязательно `{"reason": "..."}` |

- Ответ — поездка (`RideResponse`) с временами этапов `assigned_at`, `arrived_at`, `started_at`, `completed_at`, `cancelled_at` и `cancel_reason`.
- Ошибки: чужая или несуществующая поездка — `404 ride_not_found`; участник или admin без права на команду — `403 ride_command_forbidden` (admin поездками не управляет); команда не по таблице — `409 invalid_ride_transition` с `details.current_status`; причина не 1–200 символов или с управляющими символами — `422 validation_error`.
- Повтор уже применённой команды (второй `complete`, `cancel` отменённой и т. п.) — `200` с текущим состоянием, без второго события и без повторных эффектов. Завершённые, отменённые и `no_driver` поездки не оживают.
- Cancel отзывает открытое предложение (поиск больше не идёт) либо сразу освобождает назначенного водителя; `driver_id` отменённой поездки сохраняется как история. Во время `in_progress` отмены нет.
- Release: `driver_id` очищается, начинается новый 180-секундный поиск; освободивший водитель эту поездку больше не получает и не видит (`404`). Ответ — поездка после первого шага поиска (`searching` с предложением другому водителю или `no_driver`); если шаг не удался, ответ всё равно `200 searching`, поиск продолжит цикл.
- Accept предложения по отменённой поездке — `409 invalid_ride_transition`.
- История: каждый переход — строка `ride_events` (`from_status`, `to_status`, `command`, `actor_id`, `reason`, `created_at`) в той же транзакции, что и смена статуса, включая системные `assign` (accept) и `mark_no_driver` (`actor_id = null`). Координат и секретов там нет.
- `GET /rides/{id}` для пассажира и назначенного водителя активной поездки (`assigned/arrived/in_progress`) содержит `driver`: `full_name`, `phone`, `vehicle` (`make`, `model`, `color`, `plate_number`), последнюю `location` и `location_updated_at`. Admin и другие статусы — `driver: null`. Устаревшая координата поездку не завершает и не отменяет — клиент показывает время последнего обновления.
- Водитель во время поездки не уходит offline и не меняет профиль и машину (`409 driver_on_active_ride`).
- Завершение вызывает в той же транзакции точку расширения оплаты `modules/rides/completion.py::on_ride_completed` (T08 создаёт там запись неоплаченной стоимости); сейчас она ничего не делает — платежей нет.

Пример (водитель вошёл, `$RIDE_ID` — его поездка):

```bash
curl -s -b jar.txt -X POST "$API/rides/$RIDE_ID/arrive" -H "X-CSRF-Token: $CSRF"
curl -s -b jar.txt -X POST "$API/rides/$RIDE_ID/release" -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" -d '{"reason": "flat tyre"}'
```

В тестах: `support.lifecycle` — `trip_in("arrived", client, driver_factory, dispatcher)` (пассажир `pat`, водитель `dana`), `send(client, ride_id, "start", "dana")`, `ride_events(session_factory, ride_id)`; фикстура `other_client` — второй браузер на том же приложении для конкурентных запросов; хук завершения подменяется через `app.state.ride_completion_hook`.
