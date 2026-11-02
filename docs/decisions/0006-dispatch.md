# ADR 0006: Назначение ближайшего водителя и 30-секундные предложения

Дата: 3 ноября 2026 года. Статус: принято для реализации T06.

## Контекст

MVP_SPEC §6: ближайший допустимый водитель получает предложение на 30 секунд; после отказа или истечения — следующий; уже рассмотренному водителю в этом поиске повторно не предлагаем; общий бюджет поиска 180 секунд; нет кандидатов на шаге или бюджет исчерпан — `no_driver`. Состояние должно переживать перезапуск, повторный проход и два процесса не должны давать двойного назначения, поздний accept запрещён, даже если цикл не успел. Транзакции — правила T01 (ADR 0001): короткая пишущая `session.begin()`, на SQLite `BEGIN IMMEDIATE`; без внешних вызовов внутри. Правила статусов — `modules/rides/states.py` (T07A).

## Решение

### Данные

- `ride_offers`: `ride_id`, `driver_id` (→ `driver_profiles`), `status` (`pending`, `accepted`, `rejected`, `expired`, `revoked`; CHECK), `created_at`, `expires_at = created_at + OFFER_TTL_S`, `responded_at` (NULL ровно у `pending`).
- Частичные уникальные индексы `uq_ride_offers_pending_ride_id` и `uq_ride_offers_pending_driver_id`: одно `pending` на поездку и на водителя. Предикат — только `status = 'pending'`, без текущего времени: просроченное, но ещё не отмеченное предложение продолжает занимать слот, пока шаг поиска не переведёт его в `expired`. `ix_ride_offers_pending_expires_at` ускоряет поиск просроченных.
- `UNIQUE (ride_id, driver_id)`: водитель получает не больше одного предложения по поездке за всё её существование — правило «не предлагать повторно» защищено БД.
- `rides.search_started_at`, `rides.search_deadline` (NOT NULL, CHECK `deadline > started`): окно текущего поиска; при создании — `now` и `now + SEARCH_BUDGET_S`. Существующие строки заполнены миграцией как `created_at + 180 с`. Частичный индекс `ix_rides_searching_search_deadline` (`status = 'searching'`) для цикла.
- Индексы истории `rides(passenger_id, created_at, id)` и `rides(driver_id, created_at, id)`: `ORDER BY created_at DESC, id DESC` без временного B-tree (T09). Индекс по `driver_id` также обслуживает проверку «водитель занят».
- Ревизии `8deb4121d135` (rides, batch-пересоздание сохраняет CHECK и частичные индексы) и `5d2e4cb65b5e` (ride_offers). Тест сверяет каждый индекс модели, включая WHERE, с `sqlite_master` после `upgrade head` (`alembic check` предикаты не сравнивает).

### Кандидат и «ближайший»

`find_nearby_candidates` (T03) внутри транзакции вызывающего: допущен, online, есть машина, координата не старше 60 с, haversine до pickup ≤ 5 км; порядок — расстояние, затем `driver_id`. T06 добавляет в SQL `NOT EXISTS`:

- занят — поездка `assigned`/`arrived`/`in_progress` с этим водителем;
- зарезервирован — любое `pending` предложение;
- уже рассматривался в этом поиске (`for_ride_id`) — **любое** предложение по этой поездке в любом статусе.

Последнее правило выбрано как самое простое и безопасное: оно совпадает с `UNIQUE (ride_id, driver_id)`, не требует хранить попытки отдельно и автоматически исключает водителя, освободившего поездку через release (его предложение `accepted`). Следствие: после release не предлагаются и водители, отказавшиеся в первом поиске.

### Шаг поиска (`DispatchService.process_ride`)

Одна короткая пишущая транзакция на поездку:

1. `SELECT ... FOR UPDATE` поездки.
2. Условный `UPDATE ride_offers SET status='expired' WHERE ride_id=? AND status='pending' AND expires_at <= now` (граница включительно: `now >= expires_at` — истекло).
3. Поездка не `searching` — её `pending` отзывается (`revoked`), больше ничего.
4. Есть действующее `pending` — ничего.
5. `now >= search_deadline` или нет кандидата — условный `UPDATE rides SET status='no_driver' WHERE status='searching'` (переход проверяется `next_status(..., MARK_NO_DRIVER, SYSTEM_ACTOR)`).
6. Иначе INSERT предложения ближайшему кандидату в savepoint. Если уникальный индекс отказал (кандидата зарезервировал параллельный поиск), пробуется следующий из первых трёх; если отказали все — поездка остаётся `searching`, следующий проход повторит.

Шаг идемпотентен. Бюджет проверяется только перед новым предложением: последнее предложение живёт полные 30 с, поэтому поиск завершается не позже чем через `180 + 30` с. Если водителей нет уже на первом шаге, поездка сразу `no_driver` (MVP_SPEC §6); пассажир может заказать снова.

### Запуск поиска

- `POST /rides`: после коммита транзакции создания — отдельная транзакция первого шага (`start_search`); ответ показывает состояние после шага (`searching` с предложением или `no_driver`). Ошибка шага логируется, поездка остаётся `searching`, её подхватит цикл. Повтор с тем же `Idempotency-Key` возвращает текущее состояние и поиск не запускает.
- Reject: в той же транзакции сразу следующий шаг.
- Истечение: цикл; поздний accept/reject — шаг в своей транзакции.

### Ответ водителя

- Только адресат: чужое или несуществующее предложение — `404 offer_not_found` (одинаково).
- Порядок: прочитать предложение (без блокировки) → проверить адресата → `FOR UPDATE` поездки → `FOR UPDATE` предложения.
- Accept: уже `accepted` этим водителем и поездка всё ещё его — прежний успешный ответ (RideResponse). `now >= expires_at` (даже если цикл не отметил) — в той же транзакции предложение `expired`, следующий кандидат, затем `409 offer_expired`. `rejected`/`revoked` — `409 invalid_offer_transition`. Иначе `next_offer_status(..., ACCEPT)`, `next_status(..., ASSIGN, SYSTEM_ACTOR)` и два условных UPDATE (`offer ... WHERE status='pending' AND expires_at > now`, `rides ... WHERE status='searching'`); промах — 409 без назначения. Нарушение `uq_rides_active_driver_id` — `409 driver_busy`.
- Reject: повтор — прежний ответ; после срока — `409 offer_expired` и следующий кандидат; `accepted`/`revoked` — `409 invalid_offer_transition`.

### Водитель ушёл

`PUT /drivers/me/availability {"online": false}` и потеря допуска после правки профиля в той же транзакции переводят его `pending` предложение в `revoked`. Поездка остаётся `searching` без предложения; следующий проход цикла (≤ `DISPATCH_INTERVAL_S`) предлагает её следующему кандидату. Принятая поездка не затрагивается (MVP_SPEC §6).

### Фоновый цикл

`DispatchLoop` — одна asyncio-задача, запускается в lifespan при `DISPATCH_LOOP_ENABLED=true`, интервал `DISPATCH_INTERVAL_S` (1 с). Проход: read-транзакция (`read_transaction`) находит поездки с просроченным `pending`, `searching` без `pending` и не-`searching` с висящим `pending`; затем по одной пишущей транзакции на поездку. Ошибка одной поездки логируется и не мешает другим; ошибка прохода логируется (traceback — первый раз в серии), цикл продолжается. Отсутствующий файл SQLite цикл не создаёт. При остановке задача отменяется и дожидается до `engine.dispose()`. Celery, Redis и отдельного процесса нет. В тестах цикл выключен переменной окружения; тесты вызывают сервис напрямую и двигают `ManualClock`.

### Восстановление после перезапуска

В памяти процесса ничего нет: дедлайны и статусы — в БД. Первый проход после старта отмечает истёкшее, продолжает поиск или завершает его по `search_deadline`. Accept всегда сверяет срок в своей транзакции, поэтому поздний ответ до первого прохода тоже получает `409 offer_expired`.

### Порядок блокировок

`rides` → `ride_offers` во всех путях dispatch (шаг, accept, reject); `driver_profiles` dispatch только читает. Путь водителя (offline, потеря допуска): `driver_profiles` → `UPDATE ride_offers`; цикла ожидания нет, потому что dispatch не блокирует `driver_profiles`. Тест компилирует выполненные `SELECT ... FOR UPDATE` для PostgreSQL и проверяет порядок.

### Контракт для T07B

- Модель `RideOffer`, `OfferStatus`; `DispatchService(session, clock, policy)`, `DispatchPolicy.from_settings` / `DispatchPolicyDep`, `DispatchServiceDep`.
- Cancel: внутри своей транзакции (поездка уже под `FOR UPDATE`) вызвать `revoke_pending_offers(session, ride_id, now)`. Даже если забыть, шаг поиска отзовёт `pending` у поездки не в `searching`.
- Release: в своей транзакции `status = searching`, `driver_id = NULL` и `restart_search(ride, now, policy)` (новое окно 180 с); после коммита — `DispatchService.process_ride(ride_id)` (или дождаться цикла). Освободившийся водитель исключён автоматически (его `accepted` предложение).
- Принятое предложение остаётся `accepted` после release как история.

## Ограничения SQLite и PostgreSQL

- SQLite: `FOR UPDATE` опускается, пишущие транзакции сериализованы `BEGIN IMMEDIATE`; конкурентные тесты (2 корутины) доказывают отсутствие двойных предложений и назначений при таком порядке, но не пересечение транзакций.
- PostgreSQL не проверялся (ADR 0001). Типы, CHECK и частичные индексы объявлены переносимо (`sqlite_where` и `postgresql_where`). При READ COMMITTED возможна гонка: поиск прочитал водителя online, а водитель одновременно ушёл offline — предложение может остаться `pending` до истечения 30 с. Двойного назначения это не даёт (индексы и условные UPDATE).
- Расстояние — по прямой (haversine), не по дорогам; кандидаты фильтруются bounding box в SQL и дистанцией в Python.
- Нет WebSocket/SSE: водитель опрашивает `GET /drivers/me/offers`.
- Старые предложения не чистятся.
