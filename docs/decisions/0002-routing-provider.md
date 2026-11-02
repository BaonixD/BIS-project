# ADR 0002: Провайдер дорожных маршрутов — openrouteservice

Дата: 3 ноября 2026 года. Статус: принято для реализации T04 (часть A); реальная проверка — `external_pending`.

## Контекст

MVP_SPEC §5 требует реальный дорожный маршрут в Алматы через внешний сервис, бесплатный тариф с API-ключом и запрет выдавать прямое расстояние за дорожное. Первый кандидат по спецификации — openrouteservice Directions для автомобиля.

## Решение

- Провайдер: openrouteservice (HeiGIT), Directions v2, профиль `driving-car`.
- Запрос: `POST {ROUTING_BASE_URL}/v2/directions/driving-car/geojson`, базовый URL по умолчанию `https://api.openrouteservice.org`, заголовок `Authorization: <ключ>`, тело `{"coordinates": [[lon, lat], [lon, lat]]}`.
- Ответ: GeoJSON `FeatureCollection`; из `features[0]` берутся `properties.summary.distance` (м), `properties.summary.duration` (с) и `geometry` (`LineString`).
- Нормализация в `RouteResult`: `distance_m`/`duration_s` — целые, округление `ROUND_HALF_UP`; `route_geometry` — GeoJSON `LineString` с позициями `[longitude, latitude]` (только 2D, высота не запрашивается); `provider = "openrouteservice"`.
- Код: `src/taxi_service/modules/geo/` (`client.py`, `config.py`, `exceptions.py`, `schemas.py`). Настройки — `RoutingSettings` с префиксом `ROUTING_`; ключ хранится как `SecretStr` и не попадает в repr, логи и ошибки.
- Платный тариф не подключается. Используется только персональный бесплатный Standard-ключ владельца, когда он появится.

## Контракт ошибок

| Ситуация | Код | HTTP | Повтор |
| --- | --- | --- | --- |
| Нет/пустой `ROUTING_API_KEY` | `routing_unavailable` | 503 | запроса нет |
| Timeout httpx (connect/read) | `routing_provider_error`, `reason=timeout` | 503 | да |
| Исчерпан общий срок `ROUTING_TOTAL_TIMEOUT_S` во время запроса | `routing_provider_error`, `reason=timeout` | 503 | нет |
| Ошибка соединения (прочие `httpx.TransportError`) | `routing_provider_error`, `reason=connection_error` | 503 | да |
| 429 | `routing_provider_error`, `reason=rate_limited` | 503 | да |
| 5xx | `routing_provider_error`, `reason=provider_unavailable` | 503 | да |
| ORS-код 2009/2010 (точки недостижимы, маршрут не найден) | `route_not_found` | 422 | нет |
| Прочие 3xx/4xx и 2xx кроме 200 (в т.ч. 204, 401, 403 дневной квоты, 2004 лимиты, 400 без JSON) | `routing_provider_error`, `reason=rejected` | 503 | нет |
| 200 с некорректным JSON, геометрией или метриками; `httpx.DecodingError` (повреждённое сжатое тело) | `routing_provider_error`, `reason=invalid_response` | 503 | нет |
| Прочие `httpx.RequestError` (например `TooManyRedirects`) | `routing_provider_error`, `reason=rejected` | 503 | нет |

`details` содержит только `reason` и `provider_status` (HTTP-статус провайдера или `null`). Исключения провайдера не прикрепляются как `__cause__`. Ключ не попадает в ошибки, repr и логи (проверено тестом с `caplog` на серии повторов); в лог пишутся только номер попытки и `reason`. Ключ из окружения обрезается по краям, пустая строка или одни пробелы означают «не задан».

Повторы: не более `ROUTING_MAX_RETRIES` (по умолчанию 1, максимум 5), экспоненциальная задержка `ROUTING_RETRY_BACKOFF_S * 2^n` (0,5 с, 1 с, …), ограниченная `ROUTING_MAX_RETRY_DELAY_S` (5 с). `Retry-After` в форме delay-seconds используется для 429/5xx с той же верхней границей; HTTP-date и некорректные значения — обычная задержка. Ошибки соединения повторяются вместе с timeout: запрос маршрута не имеет побочных эффектов.

Общий срок: все попытки и паузы одного `get_route` укладываются в `ROUTING_TOTAL_TIMEOUT_S` (по умолчанию 10 с, максимум 60). Текущий запрос прерывается через `asyncio.timeout` → `reason=timeout`. Если следующая пауза достигла бы срока, она не выполняется и сразу возвращается последняя ошибка провайдера (например `rate_limited`). Таймауты httpx по умолчанию: connect 3 с, read 5 с; read-таймаут действует на каждое чтение, а не на весь ответ, поэтому верхнюю границу задаёт именно общий срок. Худший случай одного вызова по умолчанию ≈ 10 с.

## Сверка с документацией (3 ноября 2026, docs v10.0.1)

Сверено:

- [Directions: Requests and Return Types](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/requests-and-return-types): `POST /v2/directions/{profile}/geojson`; GeoJSON — `FeatureCollection`, маршруты в `features`, `geometry` типа `LineString`, `properties.summary` с `distance` (м) и `duration` (с).
- [Error Codes](https://giscience.github.io/openrouteservice/api-reference/error-codes): 2009 — маршрут не найден, 2010 — точка не найдена; 2004 — превышение лимитов; HTTP 400/404/500/503.
- [FAQ](https://giscience.github.io/openrouteservice/frequently-asked-questions): API ожидает и возвращает координаты `[lon, lat]`; пример квоты Directions — 2000 запросов в сутки и 40 в минуту (скользящее окно); превышение дневной квоты — 403, минутной — 429; заголовки `x-ratelimit-remaining`/`x-ratelimit-reset`; ключ принадлежит одному человеку и не используется на клиенте; условия — [HeiGIT ToS](https://account.heigit.org/info/tos).

Не сверено (страницы недоступны или не содержат сведений):

- Способ передачи ключа (`Authorization: <ключ>`) и точная схема тела запроса описаны только в интерактивном [API Playground](https://openrouteservice.org/dev/#/api-docs/directions_service); реализовано по известному контракту.
- Формат JSON-тела ошибки (`{"error": {"code", "message"}}`) и HTTP-статус, с которым приходят 2009/2010; поэтому `route_not_found` определяется по коду ошибки при любом не-200 статусе.
- Актуальные лимиты Standard-плана (страница `openrouteservice.org/plans/` вернула 404) и текст условий/атрибуции (ToS отрисовывается JavaScript и не прочитан).
- Поведение ORS для совпадающих точек не проверено; API отказывает раньше (`422 route_points_identical`, T04 часть B) и провайдер не вызывается.
- Какой заголовок ORS реально присылает при 429: `Retry-After` не подтверждён документацией; FAQ упоминает только `x-ratelimit-remaining`/`x-ratelimit-reset`. Адаптер читает лишь `Retry-After`, а `x-ratelimit-reset` пока игнорирует; при его отсутствии действует обычная задержка в пределах общего срока.

## Атрибуция

Маршруты строятся на данных OpenStreetMap (ODbL). До показа интерфейс должен выводить атрибуцию провайдера и OSM в форме, требуемой HeiGIT ToS, — например «© openrouteservice.org by HeiGIT | Map data © OpenStreetMap contributors»; точный текст подтвердить по ToS при получении ключа.

## Проверка реального маршрута

`uv run python scripts/routing_smoke.py` — один реальный запрос Абая/Достык → Аль-Фараби (Esentai). Без ключа печатает `external_pending` и завершается с кодом 2, запрос не выполняется. Pytest скрипт не запускает. Статус на 3 ноября 2026: **external_pending** — ключа нет, реальный маршрут не проверялся.

## Последствия

- Тесты адаптера используют `httpx.MockTransport` и не обращаются к сети.
- При непригодности ORS для Алматы замена провайдера оформляется отдельным ADR; интерфейс `RoutingProvider.get_route(origin, destination) -> RouteResult` и коды ошибок сохраняются.
- Внешний запрос не должен выполняться внутри транзакции БД (T05).
