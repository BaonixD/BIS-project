# ADR 0014: Свой сервер маршрутов OSRM в Docker

Дата: 3 ноября 2026 года. Статус: принято (решение владельца). Дополняет [ADR 0001](0001-sqlite-without-docker.md) и [ADR 0002](0002-routing-provider.md).

## Контекст

openrouteservice не учитывает запреты поворотов из OpenStreetMap. Пример: с ул. Индустриальной (43.267596630084, 76.922840915814348) до MEGA Alma-Ata (43.2016499, 76.8923175) ORS поворачивает налево на проспект Райымбека через двойную сплошную. OSRM на тех же данных поворачивает направо и разворачивается по боковым улицам; публичный OSRM дал 10336 м / 833 с.

## Решение

- Провайдер по умолчанию — свой OSRM (`ROUTING_PROVIDER=osrm`), openrouteservice остаётся вторым вариантом (`ROUTING_PROVIDER=openrouteservice`, `ROUTING_API_KEY`, `ROUTING_BASE_URL` без изменений).
- **Docker — только для сервера маршрутов.** Приложение, миграции, seed и тесты по-прежнему запускаются через `uv` без Docker (ADR 0001). Pytest к OSRM не обращается.
- Образ — официальный `ghcr.io/project-osrm/osrm-backend:v6.0.0` (multi-arch, на Apple Silicon работает без эмуляции). На Docker Hub `osrm/osrm-backend` нет тега `v6.0.0`, а `latest` — старая сборка только под amd64.
- `infra/osrm/docker-compose.yml`: один сервис `osrm`, `osrm-routed --algorithm mld /data/almaty.osrm`, порт `127.0.0.1:5001 → 5000` (только локально), том `infra/osrm/data` только для чтения (в `.gitignore`), `restart: unless-stopped`, `mem_limit: 1g`.
- Карта — только агломерация Алматы: `scripts/osrm_prepare.sh` скачивает `kazakhstan-latest.osm.pbf` Geofabrik (≈225 МБ, сверка MD5), вырезает bbox `76.45,43.05,77.35,43.45` (Каскелен/SDU … Талгар) локальным `osmium` (Homebrew `osmium-tool`; в образе OSRM его нет) и строит граф в одноразовых контейнерах: `osrm-extract -p /opt/car.lua`, `osrm-partition`, `osrm-customize` (лимит 2 ГБ).
- Адаптер `OsrmClient` (`modules/geo/osrm.py`): `GET {OSRM_BASE_URL}/route/v1/driving/{lon},{lat};{lon},{lat}?overview=full&geometries=geojson&steps=false`; из `routes[0]` берутся `distance`, `duration` и GeoJSON `geometry`; `provider = "osrm"`. Выбор адаптера — `create_routing_provider` (`modules/geo/providers.py`), его вызывают lifespan и `scripts/routing_smoke.py`.

## Контракт ошибок

Повторы, общий срок и коды — как в ADR 0002 (общий `RetryPolicy` и `route_with_retries` в `client.py`). Отличия OSRM:

| Ситуация | Код | Повтор |
| --- | --- | --- |
| Пустой `OSRM_BASE_URL` | `503 routing_unavailable` | запроса нет |
| Сервер отказывает в соединении (`httpx.ConnectError`: контейнер не запущен) | `503 routing_unavailable` | да |
| `code` = `NoRoute` или `NoSegment` при любом статусе | `422 route_not_found` | нет |
| Прочие 4xx (`InvalidQuery`, `TooBig`, …) и 2xx кроме 200 | `503 routing_provider_error`, `reason=rejected` | нет |
| 200 без `code: "Ok"`, без маршрута, с некорректными метриками или геометрией | `503 routing_provider_error`, `reason=invalid_response` | нет |

Timeout, прочие транспортные ошибки, 429 и 5xx — как в ADR 0002 (`timeout`, `connection_error`, `rate_limited`, `provider_unavailable`). Ключа у OSRM нет.

## Обновление карты

`scripts/osrm_prepare.sh` идемпотентен: исходник скачивается заново только если у Geofabrik файл новее (`curl --time-cond`), граф пересобирается, запущенный контейнер перезапускается на новой карте. Первый прогон на MacBook (arm64) — около 1,5 минуты с загрузкой, повторный — около 7 с; пик памяти — около 2 ГБ у `osmium extract` и около 450 МБ у `osrm-extract`; сервер держит около 90 МБ.

## Проверка

3 ноября 2026 года, данные Geofabrik того же дня: шаги OSRM (`steps=true`) на примере выше — `depart` по Индустриальной, `turn right` на Райымбека, боковые улицы (Торетай), снова Райымбека и `continue uturn`, далее Ауэзова; 10336 м, 819 с (публичный OSRM — 833 с). Quote через API с `ROUTING_PROVIDER=osrm` вернул тот же маршрут (`provider=osrm`). Pytest проверяет адаптер на `httpx.MockTransport`.

## Последствия

- Для маршрутов нужен запущенный Docker Desktop; без контейнера quote и `/geo/route` отвечают `503 routing_unavailable`.
- Данные OSM устаревают: карту нужно обновлять повторным запуском скрипта. Пробок и времени суток OSRM не учитывает, время — по профилю `car.lua`.
- Атрибуция в интерфейсе зависит от `route.provider`: для `osrm` — «Маршрут © OSRM, данные © OpenStreetMap».
