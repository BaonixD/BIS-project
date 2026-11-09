# Архитектурные решения (ADR)

Короткие записи существенных решений: контекст, выбор, последствия. Новое решение — следующий номер; принятое решение не переписывается, а заменяется новым ADR со ссылкой на прежний. Как решения сложены вместе — [architecture.md](../architecture.md).

| ADR | Решение |
| --- | --- |
| [0001](0001-sqlite-without-docker.md) | SQLite и запуск через `uv` без Docker; переносимые типы и частичные индексы, `BEGIN IMMEDIATE`, ближайший водитель — haversine с bounding box |
| [0002](0002-routing-provider.md) | Дорожные маршруты — openrouteservice Directions `driving-car`, нормализованный `RouteResult`, ошибки и повторы; дополнено ADR 0014 (OSRM по умолчанию) |
| [0003](0003-auth-sessions-csrf.md) | Серверные сессии в HttpOnly cookie, CSRF-токен сессии, проверка Origin у login/register, CORS allowlist, in-memory ограничитель входа |
| [0004](0004-payments-cash-kaspi.md) | Заменено ADR 0009. Оплата: наличные по умолчанию, Kaspi по ссылке из `KASPI_PAYMENT_URL` с ручной сверкой admin, хранение и аудит |
| [0005](0005-quotes-idempotency.md) | Quote на 5 минут со снимком цены и идемпотентное создание поездки по обязательному `Idempotency-Key` |
| [0006](0006-dispatch.md) | Назначение ближайшего водителя: предложения по одному на 30 с, бюджет поиска 180 с, фоновый цикл в процессе, порядок блокировок |
| [0007](0007-ride-lifecycle.md) | Жизненный цикл поездки: команды arrive/start/complete/cancel/release, журнал `ride_events`, гонки, карточка водителя, хук завершения |
| [0008](0008-functional-services.md) | Сервисы — функции модуля с DI через FastAPI, SQL в сервисе без слоя репозиториев, тонкие роутеры без docstring |
| [0009](0009-simple-payments.md) | Поток заменён ADR 0010; ссылка Kaspi действует. Лёгкая оплата: `cash` или `kaspi_link`, кнопка «Оплатил» пассажира сразу даёт `paid` без проверки; без `reported`, сверки и `payment_events` |
| [0010](0010-pay-before-order.md) | Оплата «как в такси»: `payment_method` в заказе, Kaspi `paid` (имитация) при назначении водителя (изменение того же дня), возврат `refunded` при отмене или `no_driver` после списания, наличные подтверждает водитель (`cash-received`) |
| [0011](0011-google-login.md) | Вход пассажиров через Google: ID token из Google Identity Services проверяет `google-auth`, аккаунт только по `google_sub`, новый — пассажир без пароля; без `GOOGLE_CLIENT_ID` выключено |
| [0012](0012-tariffs-and-car-classes.md) | Четыре тарифа `economy`/`comfort`/`comfort_plus`/`business` (`edu-v2`): quote со всеми ценами, `tariff` в заказе, класс машины `car_class` ставит admin, предложение — машине класса не ниже тарифа |
| [0013](0013-ride-ratings.md) | Оценки после `completed`: одна на сторону (`UNIQUE ride_id, rater_role`), 1–5 звёзд, теги стороны в таблице `ride_rating_tags`, `my_rating` в деталях поездки, средний рейтинг в карточке водителя, предложении, `/drivers/me` и `/users/me` |
| [0014](0014-osrm-in-docker.md) | Маршруты по умолчанию — свой OSRM (`ROUTING_PROVIDER=osrm`, `OSRM_BASE_URL`) в Docker только для сервера маршрутов: карта агломерации Алматы, `scripts/osrm_prepare.sh`; приложение и тесты без Docker; ORS — запасной вариант |
| [0015](0015-admin-management.md) | Управление доступом аккаунтов с отзывом сессий, поиск и пагинация админки, имена участников поездок и сводка сервиса |
| [0016](0016-driver-working-tariffs.md) | Максимальный класс автомобиля автоматически определяет допуск; водитель выбирает рабочие тарифы смены, dispatch учитывает оба ограничения |
