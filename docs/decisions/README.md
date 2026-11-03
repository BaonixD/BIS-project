# Архитектурные решения (ADR)

Короткие записи существенных решений: контекст, выбор, последствия. Новое решение — следующий номер; принятое решение не переписывается, а заменяется новым ADR со ссылкой на прежний. Как решения сложены вместе — [architecture.md](../architecture.md).

| ADR | Решение |
| --- | --- |
| [0001](0001-sqlite-without-docker.md) | SQLite и запуск через `uv` без Docker; переносимые типы и частичные индексы, `BEGIN IMMEDIATE`, ближайший водитель — haversine с bounding box |
| [0002](0002-routing-provider.md) | Дорожные маршруты — openrouteservice Directions `driving-car`, нормализованный `RouteResult`, ошибки и повторы; реальная проверка `external_pending` |
| [0003](0003-auth-sessions-csrf.md) | Серверные сессии в HttpOnly cookie, CSRF-токен сессии, проверка Origin у login/register, CORS allowlist, in-memory ограничитель входа |
| [0004](0004-payments-cash-kaspi.md) | Заменено ADR 0009. Оплата: наличные по умолчанию, Kaspi по ссылке из `KASPI_PAYMENT_URL` с ручной сверкой admin, хранение и аудит |
| [0005](0005-quotes-idempotency.md) | Quote на 5 минут со снимком цены и идемпотентное создание поездки по обязательному `Idempotency-Key` |
| [0006](0006-dispatch.md) | Назначение ближайшего водителя: предложения по одному на 30 с, бюджет поиска 180 с, фоновый цикл в процессе, порядок блокировок |
| [0007](0007-ride-lifecycle.md) | Жизненный цикл поездки: команды arrive/start/complete/cancel/release, журнал `ride_events`, гонки, карточка водителя, хук завершения |
| [0008](0008-functional-services.md) | Сервисы — функции модуля с DI через FastAPI, SQL в сервисе без слоя репозиториев, тонкие роутеры без docstring |
| [0009](0009-simple-payments.md) | Поток заменён ADR 0010; ссылка Kaspi действует. Лёгкая оплата: `cash` или `kaspi_link`, кнопка «Оплатил» пассажира сразу даёт `paid` без проверки; без `reported`, сверки и `payment_events` |
| [0010](0010-pay-before-order.md) | Оплата «как в такси»: `payment_method` в заказе, Kaspi сразу `paid` (имитация), возврат `refunded` при отмене или `no_driver`, наличные подтверждает водитель (`cash-received`) |
