# 0012. Четыре тарифа и класс машины

Статус: принято владельцем 3 ноября 2026 года (макет Figma). Дополняет [ADR 0005](0005-quotes-idempotency.md) (снимок цены) и [ADR 0006](0006-dispatch.md) (кандидаты).

## Контекст

В макете пассажир выбирает тариф из четырёх карточек с ценами одного маршрута, а предложение получает только машина подходящего класса. До этого был один тариф `edu-v1`, и quote хранил одну сумму.

## Решение

**Тарифы** — `economy`, `comfort`, `comfort_plus`, `business` (по возрастанию), версия `edu-v2`. Формула у всех `ROUND_HALF_UP(max(minimum, base + per_km·км + per_min·мин))` на `Decimal`:

| Тариф | base | per_km | per_min | minimum | 10 км / 25 мин |
| --- | --- | --- | --- | --- | --- |
| `economy` | 500 | 120 | 20 | 800 | 2200 |
| `comfort` | 700 | 160 | 25 | 1100 | 2925 |
| `comfort_plus` | 900 | 200 | 30 | 1500 | 3650 |
| `business` | 1200 | 260 | 40 | 2000 | 4800 |

`economy` совпадает с прежним `edu-v1`.

**Quote** хранит четыре суммы (`economy_amount_kzt`, `comfort_amount_kzt`, `comfort_plus_amount_kzt`, `business_amount_kzt`; общий CHECK `> 0`) — обычные целые колонки, переносимые на PostgreSQL. Ответ `POST /rides/quotes` вместо `amount_kzt` содержит `options: [{tariff, amount_kzt}]` — ровно четыре в порядке выше, — `tariff_version: "edu-v2"` и `kaspi_payment_url` (ссылка из `KASPI_PAYMENT_URL` или `null`), чтобы экран выбора показал кнопку Kaspi до заказа.

**Заказ.** `POST /rides {quote_id, payment_method?, tariff?}`, `tariff` по умолчанию `economy`. Как и `payment_method`, значение по умолчанию не входит в отпечаток идемпотентности: запрос без поля и с `"economy"` — один запрос; другой тариф с тем же ключом — `409 idempotency_key_reused`. Поездка хранит `tariff` (CHECK, старые — `economy`) и `amount_kzt` = сумма этого тарифа из quote; запись оплаты копирует её. `tariff` есть в `RideResponse`, деталях, истории, admin-списке и `OfferResponse`.

**Класс машины** — `vehicles.car_class` с теми же значениями (CHECK, по умолчанию `economy`), в `DriverResponse.vehicle.car_class`, в admin-списке водителей и в карточке водителя поездки (`driver.vehicle.car_class`). Класс ставит только admin: необязательное тело `POST /admin/drivers/{driver_id}/approve {"car_class": ...}` (без поля класс не меняется; `null` — 422) и `PATCH /admin/drivers/{driver_id} {"car_class": ...}` (нет водителя — `404 driver_not_found`, нет машины — `409 driver_profile_incomplete` с `missing_fields: ["vehicle"]`). `VehicleInput` водителя поля не принимает (`422`); замена машины водителем класс не сбрасывает — её всё равно заново допускает admin.

**Dispatch.** Кандидат подходит, если ранг класса его машины ≥ ранга тарифа поездки (`economy < comfort < comfort_plus < business`): фильтр `vehicles.car_class IN (...)` в том же SQL, что и прочие условия `find_nearby_candidates`. Остальные правила ADR 0006 без изменений; нет подходящего кандидата — следующий шаг или `no_driver`. Понижение класса admin в той же транзакции отзывает (`revoked`) открытые предложения водителя по тарифам выше нового класса; блокировка — `FOR NO KEY UPDATE` профиля, затем `ride_offers`, как в остальных путях водителя.

**Seed:** `demo_driver_1` — `economy`, `demo_driver_2` — `comfort`, `demo_driver_3` — `business`.

**Миграция `4dc8bde81ded`.** Четыре суммы quote: прежняя сумма становится `economy`, остальные три считаются по ставкам `edu-v2` (копия в миграции), `tariff_version` старого quote не меняется. `rides.tariff` и `vehicles.car_class` — `economy` для существующих строк. Откат оставляет у quote сумму `economy`, теряет тариф поездки и класс машины (у поездки остаётся её `amount_kzt`).

## Последствия

- Фронтенд: карточки тарифов из `options`, выбранный `tariff` в `POST /rides`; ответ quote больше не содержит `amount_kzt`.
- Существующие демо-базы получают всем машинам `economy`: seed не меняет уже созданных водителей, класс задаёт admin (`PATCH /admin/drivers/{id}`) или новая база.
- Ставки — константы кода, не настройки; смена ставок — новая версия тарифа.
