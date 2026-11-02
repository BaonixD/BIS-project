# BIS-project — Mini Taxi Service

Учебный проект по Basics of Information Systems. На текущем этапе подготовлены спецификация и пакет реализации бэкенда для Claude Code; реализованы основа приложения (T00: запуск API, health endpoints, единый формат ошибок, локальные проверки) и слой БД (T01: SQLite, Alembic, тестовая изоляция). Предметных таблиц и функциональности ещё нет.

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

Реализация собирается в `integration/backend-mvp` для итогового ревью Astra. Команды установки, миграций, запуска и проверок — в разделе [Локальная разработка](#локальная-разработка); seed появится в последующих задачах.

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

Соединения SQLite открываются с `foreign_keys=ON`, WAL и `busy_timeout=5000`; каждая транзакция начинается с `BEGIN IMMEDIATE`, поэтому пишущие транзакции выполняются по очереди (подробности — `src/taxi_service/database/sqlite.py`). Миграции работают с отключённой на время проверкой внешних ключей (пересоздание таблицы в batch-режиме иначе каскадно удалило бы связанные строки) и перед commit выполняют `PRAGMA foreign_key_check`; при нарушении вся ревизия откатывается.

Новая модель: класс от `taxi_service.database.base.Base` (время — `UtcDateTime`), импорт её модуля в `src/taxi_service/database/metadata.py`, затем `uv run alembic revision --autogenerate -m "..."`, ручная проверка ревизии, `upgrade head` и `check` на одноразовой БД. История ревизий линейная, с одной head; первая ревизия `baseline` пустая.

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
- `GET /health/ready` — `200 {"status": "ready"}`, только если БД отвечает на `SELECT 1` и её ревизия Alembic совпадает с head; иначе `503` с кодом `database_unavailable` (БД недоступна) или `database_not_migrated` (нужно `alembic upgrade head`). URL БД в ответ не попадает.
- `GET /docs` — Swagger UI, `GET /openapi.json` — схема.

Миграции и seed при запуске не выполняются; это отдельные команды. Engine создаётся в lifespan и закрывается при остановке.

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
uv run mypy src/taxi_service tests   # strict
uv run pytest                        # unit, API, интеграция с БД и миграции; без внешних сервисов
```

Тесты не используют `DATABASE_URL` и `taxi.db`: переменная удаляется из окружения теста. Шаблонная БД один раз мигрируется через Alembic во временном каталоге pytest, каждый тест получает собственную копию файла (`tests/conftest.py`: фикстуры `database_url`, `engine`, `session_factory`, `app`, `client`, `empty_database_url`). Удалять и перезаписывать файлы БД фикстуры могут только во временном каталоге pytest или если имя файла содержит слово `test` (`taxi_service.database.safety`). `:memory:` не используется: конкурентным тестам нужны независимые соединения к одному файлу.

Явное исправление стиля — отдельными командами:

```bash
uv run ruff check --fix .
uv run ruff format .
```

CI и Git hooks не настраиваются; проверки запускаются локально.

## Продукт

Алматы, KZT. Вход по username/password. Поездка предлагается ближайшему доступному водителю; 30 секунд на ответ, затем следующий. Реальный дорожный маршрут, учебный расчёт цены, наличные и Kaspi по ссылке с ручным подтверждением. Google-вход — последующий этап.

Реальный запрос маршрута потребует API-ключа, Kaspi — ссылки владельца. Секреты и локальные `.env` в Git не добавляются.
