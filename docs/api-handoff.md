# API для React-клиента

Всё, что нужно фронтенду Mini Taxi Service, без чтения кода бэкенда. Фактическая схема — OpenAPI запущенного сервера (`/openapi.json`, Swagger UI — `/docs`); этот документ сверен с ней по списку маршрутов. Устройство сервера — [architecture.md](architecture.md), запуск — [README](../README.md).

## Содержание

- [Подключение](#подключение)
- [Вход: cookie и CSRF](#вход-cookie-и-csrf)
- [Общие правила](#общие-правила)
- [Все маршруты](#все-маршруты)
- [Поток пассажира](#поток-пассажира)
- [Поток водителя](#поток-водителя)
- [Администратор](#администратор)
- [Опрос (polling)](#опрос-polling)
- [Оплата](#оплата)
- [Карта и маршрут](#карта-и-маршрут)
- [Коды ошибок](#коды-ошибок)

## Подключение

- Базовый URL API: `http://localhost:8000/api/v1` (локальный запуск по README). Health-маршруты — без префикса: `/health/live`, `/health/ready`.
- Swagger UI: `http://localhost:8000/docs`, схема: `http://localhost:8000/openapi.json`. Из схемы можно сгенерировать типы (например, `openapi-typescript`). OpenAPI перечисляет только HTTP-статусы ошибок маршрута; коды `error.code` и правила — в этом документе.
- Origin фронтенда должен быть в `CORS_ALLOWED_ORIGINS` в `.env` сервера (через запятую, без `*`; в `.env.example` уже `http://localhost:5173` — dev-сервер Vite). CORS работает с credentials; разрешены методы `GET, POST, PUT, PATCH, DELETE`, заголовки `Content-Type`, `X-CSRF-Token`, `X-Request-ID`, `Idempotency-Key`; клиенту доступны ответные заголовки `X-Request-ID` и `Idempotent-Replayed`.
- Cookie сессии `SameSite=Lax`: браузер отправит её в `fetch` только между адресами одного сайта. Открывайте фронтенд и API на одном хосте — оба `localhost` (порты могут различаться), не смешивайте `localhost` и `127.0.0.1`. Для локального `http://` сервер запускается с `SESSION_COOKIE_SECURE=false` (так в `.env.example`), иначе браузер не вернёт cookie.
- Альтернатива — прокси dev-сервера (`/api` → `http://localhost:8000`): тогда запросы same-origin и CORS не нужен.

## Вход: cookie и CSRF

Сессия — HttpOnly cookie `taxi_session` (7 дней), JavaScript её не видит. Каждый изменяющий запрос (`POST`, `PUT`, `PATCH`, `DELETE`) с сессией требует заголовок `X-CSRF-Token` с `csrf_token` этой сессии, иначе `403 csrf_failed`. `GET` токена не требует.

1. `POST /auth/register` `{username, password, role}` — `role`: `passenger` или `driver` (admin не регистрируется через API). Username 3–32 символа `[A-Za-z0-9_]`, уникален без учёта регистра; пароль 10–128 символов. Ответ `201` — пользователь, без входа.
2. `POST /auth/login` `{username, password}` → `200 {user, csrf_token, expires_at}` и cookie. Сохраните `csrf_token` в памяти приложения.
3. При загрузке страницы: `GET /auth/session` → `200 {user, csrf_token, expires_at}` (восстановить пользователя и токен) или `401 not_authenticated` (показать вход).
4. `POST /auth/logout` с `X-CSRF-Token` → `204`, cookie удаляется, старый токен больше не работает.

- Login и register проверяют заголовок `Origin`: браузерный запрос с origin не из `CORS_ALLOWED_ORIGINS` получает `403 origin_not_allowed`. Браузер ставит `Origin` сам — ничего добавлять не нужно.
- Неверный пароль и неизвестный username дают одинаковый `401 invalid_credentials`. Больше 5 попыток на username за 15 минут — `429 too_many_attempts` с `details.retry_after_seconds`.
- Новый вход в том же браузере отзывает прежнюю сессию; после него используйте новый `csrf_token`.
- Все `fetch` — с `credentials: "include"`.

```ts
const API = "http://localhost:8000/api/v1";
let csrfToken: string | null = null;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string,
              public details: Record<string, unknown>, public requestId: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: { method?: string; body?: unknown;
                             headers?: Record<string, string> } = {}): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { ...init.headers };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(API + path, {
    method,
    headers,
    credentials: "include",
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (!response.ok) {
    const { code, message, details } = data.error;
    throw new ApiError(response.status, code, message, details, data.request_id);
  }
  return data as T;
}

export async function login(username: string, password: string) {
  const session = await api<{ csrf_token: string }>("/auth/login",
    { method: "POST", body: { username, password } });
  csrfToken = session.csrf_token;
  return session;
}

export async function restoreSession() {
  try {
    const session = await api<{ csrf_token: string }>("/auth/session");
    csrfToken = session.csrf_token;
    return session;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
```

На `401 not_authenticated` в любом запросе — сессия истекла или отозвана: показать вход. На `403 csrf_failed` — перечитать `GET /auth/session` и повторить запрос один раз.

### Вход через Google (пассажиры)

Решение — [ADR 0011](decisions/0011-google-login.md). Реальный вход с настоящим Client ID пока **external_pending**: Client ID ещё не выдан.

1. При загрузке экрана входа: `GET /auth/providers` → `{google_client_id: string | null}`. `null` — Google-вход выключен на сервере, кнопку не показывать.
2. Кнопка — [Google Identity Services](https://developers.google.com/identity/gsi/web/guides/display-button): скрипт `https://accounts.google.com/gsi/client`, `google.accounts.id.initialize({client_id, callback})`, `google.accounts.id.renderButton(...)`. Callback получает `response.credential` — Google ID token (JWT). Origin фронтенда (`http://localhost:5173`) должен быть в **Authorized JavaScript origins** OAuth-клиента и в `CORS_ALLOWED_ORIGINS` сервера.
3. `POST /auth/google` `{credential}` → как login: `200 {user, csrf_token, expires_at}` и cookie `taxi_session`. Сохраните `csrf_token`; дальше всё как после обычного входа.

- Первый вход создаёт **пассажира**: username из части email до `@` (`Alice.Smith@gmail.com` → `alice_smith`; занято — `alice_smith_2` …), `display_name` профиля — имя из Google. Повторный вход тем же Google-аккаунтом возвращает того же пользователя. Аккаунт с тем же email или username не связывается — получится отдельный пассажир.
- У Google-пользователя нет пароля: `POST /auth/login` с его username всегда `401 invalid_credentials`.
- Ошибки: `401 invalid_google_token` (подпись, срок, чужой `aud`, email не подтверждён) — снова показать кнопку; `503 google_login_unavailable` — на сервере нет `GOOGLE_CLIENT_ID` или Google недоступен; `403 origin_not_allowed`; `429 too_many_attempts` — больше 5 входов одного Google-аккаунта за 15 минут.

```ts
export async function googleClientId(): Promise<string | null> {
  return (await api<{ google_client_id: string | null }>("/auth/providers")).google_client_id;
}

export async function loginWithGoogle(credential: string) {
  const session = await api<{ csrf_token: string }>("/auth/google",
    { method: "POST", body: { credential } });
  csrfToken = session.csrf_token;
  return session;
}

// google.accounts.id.initialize({ client_id, callback: ({ credential }) => loginWithGoogle(credential) });
```

## Общие правила

- JSON, UUID для идентификаторов, время — UTC ISO 8601 с `Z` (`"2026-11-03T09:00:00.123456Z"`); показывать в часовом поясе пользователя (Алматы).
- Координаты — объект `{"longitude": 76.9457, "latitude": 43.2383}` (WGS 84): сначала долгота, числа JSON, `longitude` −180…180, `latitude` −90…90.
- Расстояние — целые метры (`distance_m`), длительность — секунды (`duration_s`), сумма — целые тенге (`amount_kzt`) и `currency: "KZT"`.
- Тела запросов закрыты: лишние поля (сумма, статус, водитель и т. п.) дают `422 validation_error`. В `PATCH` пропущенное поле не меняется, `null` запрещён.
- Статусы меняются только именованными командами (`/arrive`, `/cancel`, `/payment/cash-received`…), не через `PATCH`.
- Каждый ответ содержит `X-Request-ID`; прикладывайте его к сообщениям об ошибке.

### Формат ошибки

```json
{"error": {"code": "invalid_ride_transition", "message": "...", "details": {"current_status": "completed", "command": "cancel"}},
 "request_id": "4ee5beba442744609642772e82dc4074"}
```

Ориентируйтесь на `error.code` (стабилен), а не на `message` (английский текст для разработчика). У `422 validation_error` в `details.errors` — список `{loc, msg, type}` без присланных значений; `loc` указывает поле (`["body", "pickup", "latitude"]`).

### Пагинация

Списки возвращают `{"items": [...], "limit": 20, "offset": 0, "total": 57}`. Параметры `limit` (1–100, по умолчанию 20) и `offset` (≥ 0). Порядок — новые сначала (`created_at DESC, id DESC`). `offset` за концом — пустой `items` с верным `total`.

Фильтры истории (`GET /rides`, `GET /admin/rides`): `status` (повторяемый: `?status=completed&status=cancelled`), `created_from` (включительно) и `created_to` (исключительно) — ISO 8601 обязательно со смещением (`2026-11-03T09:00:00Z`; `+` в URL кодируется как `%2B`); без смещения — `422 validation_error`, `created_from > created_to` — `422 invalid_date_range`.

### Idempotency-Key для `POST /rides`

- Заголовок обязателен: `Idempotency-Key: <UUID>` (1–128 видимых ASCII). Без него — `422 idempotency_key_required`, неверный формат — `422 idempotency_key_invalid`. В OpenAPI он помечен обязательным; изменяющие запросы там требуют cookie сессии и `X-CSRF-Token` вместе, чтения — только cookie.
- Генерируйте новый ключ на каждую попытку заказа (нажатие «Заказать») и **переиспользуйте тот же ключ** при сетевом повторе этого же заказа. Повтор с тем же ключом и телом возвращает ту же поездку (`201`, заголовок `Idempotent-Replayed: true`) с её текущим состоянием; тот же ключ с другим `quote_id` — `409 idempotency_key_reused`.
- Ошибка (например, `409 quote_expired`) ключ не занимает: повтор с ним выполнится заново.

## Все маршруты

Пути после `http://localhost:8000`. Роль «вошедший» — любая роль с сессией. Все изменяющие маршруты под `/api/v1` требуют `X-CSRF-Token`, кроме `register`, `login` и `auth/google`.

| Метод | Путь | Кто | Тело → ответ |
| --- | --- | --- | --- |
| GET | `/health/live` | все | → `{status: "ok"}` |
| GET | `/health/ready` | все | → `{status: "ready"}` или `503 database_unavailable` / `database_not_migrated` |
| POST | `/api/v1/auth/register` | без сессии | `{username, password, role}` → `201 UserResponse` |
| POST | `/api/v1/auth/login` | без сессии | `{username, password}` → `SessionResponse` + cookie |
| GET | `/api/v1/auth/providers` | все | → `{google_client_id: string \| null}` |
| POST | `/api/v1/auth/google` | без сессии | `{credential}` (Google ID token) → `SessionResponse` + cookie |
| GET | `/api/v1/auth/session` | вошедший | → `SessionResponse {user, csrf_token, expires_at}` |
| POST | `/api/v1/auth/logout` | вошедший | → `204` |
| GET | `/api/v1/users/me` | вошедший | → `{id, username, role, created_at, display_name, phone, rating, login_method, email}` |
| PATCH | `/api/v1/users/me` | вошедший | `{display_name?, phone?}` → то же (роль и username не меняются) |
| GET | `/api/v1/drivers/me` | driver | → `DriverResponse` |
| PATCH | `/api/v1/drivers/me` | driver | `{full_name?, phone?, license_number?, vehicle?: {make, model, color, plate_number, year}}` → `DriverResponse` (класс машины водитель не задаёт) |
| PUT | `/api/v1/drivers/me/availability` | driver | `{online: bool}` → `DriverResponse` |
| PUT | `/api/v1/drivers/me/location` | driver | `{longitude, latitude}` → `DriverResponse` |
| GET | `/api/v1/drivers/me/offers` | driver | `?limit&offset` → `Page<OfferResponse>` (не больше одного открытого) |
| POST | `/api/v1/ride-offers/{offer_id}/accept` | адресат предложения | → `RideResponse` (`assigned`) |
| POST | `/api/v1/ride-offers/{offer_id}/reject` | адресат предложения | → `OfferResponse` (`rejected`) |
| POST | `/api/v1/geo/route` | вошедший | `{origin, destination}` → `RouteResult` (без цены) |
| POST | `/api/v1/rides/quotes` | passenger | `{pickup, dropoff}` → `201 QuoteResponse` |
| POST | `/api/v1/rides` | passenger | `{quote_id, payment_method?, tariff?}` + `Idempotency-Key` → `201 RideResponse` |
| GET | `/api/v1/rides` | passenger, driver | `?status&created_from&created_to&limit&offset` → `Page<RideSummary>` |
| GET | `/api/v1/rides/{ride_id}` | пассажир поездки, назначенный водитель, admin | → `RideDetailsResponse` (`RideResponse` + `driver`) |
| POST | `/api/v1/rides/{ride_id}/arrive` | назначенный водитель | → `RideResponse` |
| POST | `/api/v1/rides/{ride_id}/start` | назначенный водитель | → `RideResponse` |
| POST | `/api/v1/rides/{ride_id}/complete` | назначенный водитель | → `RideResponse` |
| POST | `/api/v1/rides/{ride_id}/cancel` | пассажир поездки | без тела или `{reason}` → `RideResponse` |
| POST | `/api/v1/rides/{ride_id}/release` | назначенный водитель | `{reason}` (обязательно) → `RideResponse` |
| GET | `/api/v1/rides/{ride_id}/payment` | пассажир, назначенный водитель, admin | → `PaymentResponse` |
| POST | `/api/v1/rides/{ride_id}/payment/cash-received` | назначенный водитель | без тела → `PaymentResponse` |
| POST | `/api/v1/rides/{ride_id}/rating` | пассажир поездки, назначенный водитель | `{stars, tags?, comment?}` → `201 RatingResponse` (после `completed`) |
| GET | `/api/v1/admin/drivers` | admin | `?approval_status=pending\|approved&limit&offset` → `Page<AdminDriverResponse>` |
| POST | `/api/v1/admin/drivers/{driver_id}/approve` | admin | без тела или `{car_class?}` → `AdminDriverResponse` |
| PATCH | `/api/v1/admin/drivers/{driver_id}` | admin | `{car_class}` → `AdminDriverResponse` |
| GET | `/api/v1/admin/rides` | admin | фильтры истории + `passenger_id`, `driver_id` → `Page<RideSummary>` |
| GET | `/api/v1/admin/users` | admin | `?role&limit&offset` → `Page<AdminUserResponse>` |

Основные схемы ответа (поля — как в OpenAPI):

- `RideResponse`: `id`, `status`, `passenger_id`, `driver_id`, `quote_id`, `pickup`, `dropoff`, `route` (`RouteResult`), `tariff`, `amount_kzt` (цена выбранного тарифа), `currency`, `tariff_version`, `created_at`, `updated_at`, `assigned_at`, `arrived_at`, `started_at`, `completed_at`, `cancelled_at`, `cancel_reason`, `payment_method`, `payment_status`.
- `RideDetailsResponse` = `RideResponse` + `my_rating` (`{stars, tags, comment}` — своя оценка, `null` до неё и у admin) + `driver`: для пассажира и назначенного водителя при `assigned`/`arrived`/`in_progress` — `{full_name, phone, vehicle: {make, model, color, plate_number, car_class}, location, location_updated_at, rating}`; при `completed` — та же карточка для чека, но `location` и `location_updated_at` = `null`; иначе `null`.
- `RouteResult`: `distance_m`, `duration_s`, `route_geometry` (GeoJSON `LineString`), `provider`.
- `QuoteResponse`: `quote_id`, `pickup`, `dropoff`, `route`, `options` (ровно четыре `{tariff, amount_kzt}`: `economy`, `comfort`, `comfort_plus`, `business`), `currency`, `tariff_version` (`edu-v2`), `kaspi_payment_url` (ссылка Kaspi или `null`), `created_at`, `expires_at`. Общей `amount_kzt` нет.
- `OfferResponse`: `id`, `ride_id`, `status`, `pickup`, `dropoff`, `distance_m`, `duration_s`, `amount_kzt`, `currency`, `tariff`, `payment_method` (`cash` | `kaspi_link`), `passenger_rating`, `created_at`, `expires_at`.
- `MyProfileResponse` (`/users/me`): `id`, `username`, `role`, `created_at`, `display_name`, `phone`, `rating`, `login_method` (`password` | `google` — у аккаунта, созданного входом через Google), `email` (email Google-аккаунта; у входа по паролю `null`).
- `RatingSummary` (`rating`, `passenger_rating`): `{average: float | null, count: int}` — среднее полученных звёзд (два знака), без оценок `null`/`0`.
- `RatingResponse`: `ride_id`, `rater_role` (`passenger|driver`), `stars`, `tags`, `comment`, `created_at`.
- `RideSummary` (элемент истории): `id`, `status`, `passenger_id`, `driver_id`, `pickup`, `dropoff`, `distance_m`, `duration_s`, `amount_kzt`, `currency`, `tariff`, `created_at`, `updated_at`, `payment_status`, `payment_method` (есть с момента заказа). Геометрии нет — за ней `GET /rides/{ride_id}`.
- `DriverResponse`: `id`, `full_name`, `phone`, `license_number`, `vehicle` (`{make, model, color, plate_number, year, car_class}` или `null`), `approval_status`, `approved_at`, `online`, `location`, `location_updated_at`, `missing_fields`, `rating`. `AdminDriverResponse` дополнительно: `username`, `created_at`, `approved_by`.
- `PaymentResponse`: `ride_id`, `amount_kzt`, `currency`, `method`, `status`, `paid_at`, `refunded_at`, `payment_url` (ссылка Kaspi только при `kaspi_link`, иначе `null`).

Тариф поездки и класс машины — `economy` < `comfort` < `comfort_plus` < `business` ([ADR 0012](decisions/0012-tariffs-and-car-classes.md)). Статусы: поездка — `searching`, `assigned`, `arrived`, `in_progress`, `completed`, `cancelled`, `no_driver`; предложение — `pending`, `accepted`, `rejected`, `expired`, `revoked`; оплата — `unpaid`, `paid`, `refunded`; метод — `cash`, `kaspi_link`. Диаграммы — в [architecture.md](architecture.md#состояния).

## Поток пассажира

1. **Регистрация и вход**: `POST /auth/register` (`role: "passenger"`), `POST /auth/login`, сохранить `csrf_token`. Или [через Google](#вход-через-google-пассажиры): `POST /auth/google` создаёт пассажира при первом входе. По желанию `PATCH /users/me {display_name, phone}`.
2. **Активная поездка после перезагрузки**: `GET /rides?status=searching&status=assigned&status=arrived&status=in_progress&limit=1` — если есть элемент, сразу открыть экран поездки.
3. **Выбор точек** на карте (адресного поиска на сервере нет) и **цена**: `POST /rides/quotes {pickup, dropoff}` → показать карточки тарифов из `options` (`tariff`, `amount_kzt`), маршрут (`route.route_geometry`), `route.distance_m`, `route.duration_s`. Quote действует 5 минут (`expires_at`); после — запросить новый. Ошибки: `503 routing_unavailable` (на сервере нет ключа маршрутов), `503 routing_provider_error`, `422 route_not_found`, `422 route_points_identical`; при ошибке quote не создаётся.
4. **Заказ**: выбрать тариф и способ оплаты ([Оплата](#оплата)), затем `POST /rides {quote_id, payment_method, tariff}` с новым `Idempotency-Key` → `201` (без `tariff` — `economy`). Предложение получают только машины класса не ниже тарифа: для `business` при одних `economy`-водителях рядом сразу `no_driver`. Ответ уже после первого шага поиска: `searching` (предложение отправлено ближайшему водителю) или сразу `no_driver` (рядом нет свободных водителей). Цена берётся только из quote. Ошибки: `409 active_ride_exists`, `409 quote_expired`, `409 quote_already_used`, `404 quote_not_found` (неизвестный или чужой quote), `503 kaspi_unavailable` (Kaspi не настроен — заказать наличными). Повтор с тем же ключом поиск заново не запускает.
5. **Ожидание**: опрашивать `GET /rides/{ride_id}`. `searching` может длиться до ~3,5 минут (водители получают предложение по очереди); `no_driver` — поиск закончился, предложить заказать снова (новый quote).
6. **Водитель назначен** (`assigned`): показать `driver` — имя, телефон, машину, позицию и `location_updated_at` (если позиция давно не обновлялась — показать «обновлено N мин назад»; поездка от этого не отменяется). Далее `arrived` (водитель на месте) → `in_progress` → `completed`.
7. **Отмена**: `POST /rides/{ride_id}/cancel` (тело необязательно, `{"reason": "..."}` 1–200 символов) в `searching`/`assigned`/`arrived`. В `in_progress` отмены нет (`409 invalid_ride_transition`). Открытое предложение водителю отзывается, назначенный водитель сразу свободен. Повтор — `200` с тем же состоянием.
8. **Release водителем**: поездка возвращается из `assigned`/`arrived` в `searching`, `driver` пропадает — показать «ищем другого водителя», продолжать опрос.
9. **Оплата**: Kaspi списывается при назначении водителя (`payment_status: "paid"` в ответе после `assigned`); наличные отдать водителю после `completed`, он подтверждает. Раздел [Оплата](#оплата).
10. **История**: `GET /rides?limit=20&offset=0`, фильтр `status`; детали — `GET /rides/{ride_id}`.
11. **Оценка водителя** после `completed`: `POST /rides/{ride_id}/rating {"stars": 5, "tags": ["polite", "clean_car"], "comment": "..."}` → `201`. Теги пассажира: `polite`, `clean_car`, `smooth_driving`, `knows_route`. Показывать форму, пока `my_rating` в `GET /rides/{ride_id}` равен `null`. Раздел [Оценки](#оценки).

## Поток водителя

1. **Регистрация и вход** с `role: "driver"`.
2. **Профиль**: `GET /drivers/me` → `missing_fields` показывает, чего не хватает. `PATCH /drivers/me {full_name, phone, license_number, vehicle: {make, model, color, plate_number, year}}`. Телефон нормализуется в `+цифры`, номер прав и госномер — заглавными без пробелов и `-`; госномер уникален (`409 plate_number_taken`); год — от 1980 до следующего года. `vehicle` заменяет машину целиком.
3. **Ожидание допуска**: `approval_status: "pending"` до решения admin; опрашивать `GET /drivers/me` редко (раз в 10–30 с) или по кнопке. Изменение ФИО, прав или машины у допущенного водителя возвращает его в `pending` и offline; телефон меняется без этого.
4. **На линии**: `PUT /drivers/me/availability {"online": true}` (только допущенному: иначе `409 driver_not_approved` / `driver_profile_incomplete`). Пока online — отправлять `PUT /drivers/me/location {longitude, latitude}` примерно раз в 10 с: водитель без координаты свежее 60 с предложений не получает. `location_updated_at` ставит сервер.
5. **Предложения**: опрашивать `GET /drivers/me/offers`; в `items` не больше одного предложения с `expires_at` (30 с) — показать отсчёт по серверному `expires_at`. `POST /ride-offers/{offer_id}/accept` → `RideResponse` (`assigned`), сохранить `id` поездки. `POST /ride-offers/{offer_id}/reject` → предложение уходит следующему водителю; повтор reject возвращает то же отклонённое предложение. Предложение пропадает из списка, когда на него ответили, оно истекло или отозвано. Ошибки: `409 offer_expired` (не успел — убрать карточку), `409 driver_busy`, `409 invalid_offer_transition`, `409 invalid_ride_transition` (пассажир уже отменил), `404 offer_not_found`. Повтор accept — тот же ответ.
6. **Поездка**: `POST /rides/{ride_id}/arrive` → `/start` → `/complete`; повтор уже применённой команды возвращает поездку без изменений. Состояние и данные пассажира берутся из `GET /rides/{ride_id}`; опрашивать его, чтобы увидеть отмену пассажиром (`cancelled`). Во время поездки нельзя уйти offline и менять профиль (`409 driver_on_active_ride`).
7. **Освободить заказ** до начала: `POST /rides/{ride_id}/release {"reason": "..."}` (причина обязательна, 1–200 символов). Ответ — поездка, какой её оставил release: `searching` без водителя или сразу `no_driver`; дальнейшие изменения в него не попадают. После этого поездка водителю недоступна (`404`), повторно её не предложат.
8. **Оплата**: `GET /rides/{ride_id}/payment` (сумма, способ, статус). Если `method: "cash"`, после `completed` получить деньги и нажать «Наличные получены»: `POST /rides/{ride_id}/payment/cash-received`.
9. **Активная поездка после перезагрузки**: `GET /rides?status=assigned&status=arrived&status=in_progress&limit=1`. История — `GET /rides`: поездки, где он сейчас водитель (освобождённая уходит из истории).
10. **Конец смены**: `PUT /drivers/me/availability {"online": false}` — открытое предложение отзывается.
11. **Оценка пассажира** после `completed`: `POST /rides/{ride_id}/rating {"stars": 5, "tags": ["on_time"]}`; теги водителя: `on_time`, `polite`, `clean`. В предложении виден `passenger_rating`, в `GET /drivers/me` — свой `rating`.

## Администратор

Admin создаётся только локальной командой (`scripts/create_admin.py`, README), публичной регистрации нет.

- Допуск водителей: `GET /admin/drivers?approval_status=pending` (новые регистрации сначала; водитель без профиля — тоже `pending`) → `POST /admin/drivers/{driver_id}/approve` (`driver_id` — id пользователя; необязательное тело `{"car_class": "comfort"}` сразу задаёт класс, без него класс не меняется).
- Класс машины: `PATCH /admin/drivers/{driver_id} {"car_class": "business"}` (`404 driver_not_found`, без машины — `409 driver_profile_incomplete`). Понижение класса отзывает открытые предложения водителя по более высоким тарифам. У новой машины — `economy`. Неполный профиль — `409 driver_profile_incomplete` с `details.missing_fields`; повторный допуск возвращает первый.
- Чтение: `GET /admin/rides` (фильтры истории, `passenger_id`, `driver_id`; неизвестный id — пустая страница), `GET /admin/users?role=driver`, любая поездка `GET /rides/{ride_id}` (без карточки водителя) и её оплата.
- Командами поездки и оплаты admin не управляет (`403 ride_command_forbidden`, `403 payment_action_forbidden`); `GET /rides` для admin — `403 forbidden`.

## Оценки

[ADR 0013](decisions/0013-ride-ratings.md). Только после `completed`, по одной оценке на сторону, изменить нельзя.

- Тело: `stars` — целое 1–5; `tags` — массив (по умолчанию `[]`, повторы отбрасываются, ответ в фиксированном порядке); `comment` — до 500 символов после обрезки, пустой — `null`.
- Ошибки по порядку: `404 ride_not_found` (нет поездки или чужая), `403 rating_forbidden` (admin), `422 validation_error` (тег другой стороны — `details.errors[].loc = ["body", "tags", i]`; звёзды вне 1–5, неизвестный тег, лишнее поле), `409 ride_not_completed`, `409 rating_already_exists`. Требует `X-CSRF-Token`.
- Своя оценка — `my_rating` в `GET /rides/{ride_id}`. Средние (`{average, count}`): водителя — `driver.rating` в деталях поездки и `rating` в `/drivers/me`, пассажира — `passenger_rating` в предложении; свой — `rating` в `/users/me`.

## Опрос (polling)

WebSocket и SSE нет. Сервер обрабатывает истечения раз в секунду, поэтому опрос чаще 1–2 с не нужен; не опрашивайте скрытую вкладку (`document.visibilityState`).

| Что | Кто | Как часто | Когда прекращать |
| --- | --- | --- | --- |
| `GET /rides/{ride_id}` | пассажир | 2–3 с при `searching`, 3–5 с при `assigned`/`arrived`/`in_progress` | `completed`, `cancelled`, `no_driver` |
| `GET /rides/{ride_id}` | водитель | 3–5 с во время поездки (видеть отмену) | `completed`, `cancelled`, `404` после release |
| `GET /drivers/me/offers` | водитель | 2 с, пока online и нет активной поездки | offline или принятая поездка |
| `PUT /drivers/me/location` | водитель | ~10 с, пока online (порог свежести 60 с) | offline |
| `GET /drivers/me` | водитель | 10–30 с, пока `pending` | `approved` |

Отсчёт времени предложения и quote считайте от серверных `expires_at`, не от локального времени нажатия.

## Оплата

Оплата «как в такси» ([ADR 0010](decisions/0010-pay-before-order.md)): способ выбирается до заказа. Проект учебный — реальных списаний и возвратов нет, `paid` и `refunded` только отметки, сервер не проверяет поступление денег.

Запись оплаты создаётся вместе с поездкой (сумма = `amount_kzt`) и видна сразу: `GET /rides/{ride_id}/payment`.

Поток пассажира:

1. **Экран заказа**: выбрать «Наличные» (`cash`, по умолчанию) или «Kaspi» (`kaspi_link`).
2. **Kaspi**: ссылка есть уже в quote (`kaspi_payment_url`; `null` — Kaspi на сервере не настроен, скрыть кнопку). `POST /rides {quote_id, "payment_method": "kaspi_link", tariff}` → оплата `unpaid`; когда водитель принимает заказ (`assigned`), сервер переводит её в `paid` (`paid_at`, имитация списания). Ссылку можно открыть на телефоне или показать QR; сумму покупатель вводит сам — показать `amount_kzt` выбранного тарифа. Та же ссылка — `payment_url` в `GET /rides/{ride_id}/payment`. `503 kaspi_unavailable` при заказе — Kaspi не настроен: заказать наличными.
3. **Наличные**: `POST /rides {quote_id}` (или `"payment_method": "cash"`) → `unpaid`. После поездки отдать деньги водителю.
4. **Отмена или `no_driver`**: до назначения водителя Kaspi остаётся `unpaid` (ничего не списано); после — `refunded` (`refunded_at`). Наличные остаются `unpaid`. Release водителем оплату не меняет: списанная остаётся за следующим водителем.

Поток водителя (наличные): после `completed` — `POST /rides/{ride_id}/payment/cash-received` → `paid`, `paid_at`. Повтор — `200` с тем же ответом.

- `GET` видят пассажир, назначенный водитель и admin; посторонний — `404 ride_not_found`.
- `cash-received`: только назначенный водитель (пассажир, admin — `403 payment_action_forbidden`); до `completed` — `409 ride_not_completed`; у `kaspi_link` — `409 invalid_payment_transition`. Требует `X-CSRF-Token`.
- Способ после заказа не меняется: для другого способа отменить поездку и заказать заново.
- `payment_url` приходит при `kaspi_link`, у `cash` — `null`.
- `payment_method` и `payment_status` есть в `RideResponse`, деталях поездки, истории (`GET /rides`) и `GET /admin/rides`.

## Карта и маршрут

- `route.route_geometry` в quote и поездке — GeoJSON `{"type": "LineString", "coordinates": [[lon, lat], ...]}`. MapLibre/OpenLayers принимают его как есть; **Leaflet ждёт `[lat, lon]`** — используйте `L.geoJSON(...)` или переставьте пары.
- Точки посадки и высадки — `pickup`, `dropoff` (`{longitude, latitude}`); позиция водителя — `driver.location` из `GET /rides/{ride_id}`.
- `POST /geo/route` строит маршрут без цены (например, для предпросмотра); для заказа используйте `POST /rides/quotes` — там маршрут и цена. Ошибки — как у quote; при совпадающих точках провайдер не вызывается (`422 route_points_identical`).
- Маршруты строит openrouteservice на данных OpenStreetMap: интерфейс с маршрутом должен показывать атрибуцию, например «© openrouteservice.org by HeiGIT | Map data © OpenStreetMap contributors» (точный текст — по условиям HeiGIT). Подложку карты (тайлы) фронтенд выбирает сам и выводит её атрибуцию; публичные тайлы OSM имеют свою политику использования.
- Ключ маршрутизации есть только на сервере; на клиенте он не нужен и не используется.
- Пока у сервера нет `ROUTING_API_KEY`, quote отвечает `503 routing_unavailable` — это ожидаемое состояние локального стенда (реальная маршрутизация `external_pending`).

## Коды ошибок

| HTTP | Код | Где | Что показать / сделать |
| --- | --- | --- | --- |
| 401 | `not_authenticated` | любой маршрут с сессией | экран входа |
| 401 | `invalid_credentials` | login | «неверный логин или пароль» |
| 401 | `invalid_google_token` | `auth/google` | токен Google недействителен или email не подтверждён: войти через Google снова |
| 403 | `csrf_failed` | изменяющие запросы | перечитать `GET /auth/session`, повторить |
| 403 | `origin_not_allowed` | login, register, `auth/google` | конфигурация: origin не в `CORS_ALLOWED_ORIGINS` |
| 403 | `forbidden` | маршруты с ролью | роль не подходит |
| 409 | `username_taken` | register | занято (без учёта регистра) |
| 429 | `too_many_attempts` | login, `auth/google` | подождать `details.retry_after_seconds` |
| 503 | `google_login_unavailable` | `auth/google` | Google-вход выключен или Google недоступен: скрыть кнопку, вход по паролю |
| 404 | `driver_not_found` | approve | нет такого водителя |
| 409 | `driver_profile_incomplete` | availability, approve | `details.missing_fields` |
| 409 | `driver_not_approved` | availability | ждать допуска |
| 409 | `driver_on_active_ride` | availability offline, PATCH `/drivers/me` | завершить поездку |
| 409 | `plate_number_taken` | PATCH `/drivers/me` | госномер уже у другого водителя |
| 422 | `route_points_identical` | quote, `/geo/route` | точки совпадают |
| 422 | `route_not_found` | quote, `/geo/route` | между точками нет дорожного маршрута |
| 503 | `routing_unavailable` | quote, `/geo/route` | на сервере не задан ключ маршрутов |
| 503 | `routing_provider_error` | quote, `/geo/route` | сбой провайдера, `details.reason`: `timeout`, `connection_error`, `rate_limited`, `provider_unavailable`, `rejected`, `invalid_response`; можно повторить позже |
| 404 | `quote_not_found` | `POST /rides` | новый quote |
| 409 | `quote_expired`, `quote_already_used` | `POST /rides` | новый quote |
| 409 | `active_ride_exists` | `POST /rides` | открыть текущую поездку |
| 422 | `idempotency_key_required`, `idempotency_key_invalid` | `POST /rides` | ошибка клиента |
| 409 | `idempotency_key_reused` | `POST /rides` | новый ключ для нового заказа |
| 404 | `ride_not_found` | поездка и оплата | нет доступа или не существует |
| 403 | `ride_command_forbidden` | команды поездки | роль участника не та (`details.command`) |
| 409 | `invalid_ride_transition` | команды поездки, accept | `details.current_status`, `details.command`; перечитать поездку |
| 404 | `offer_not_found` | accept, reject | убрать карточку |
| 409 | `offer_expired` | accept, reject | срок вышел, убрать карточку |
| 409 | `invalid_offer_transition` | accept, reject | предложение уже не открыто |
| 409 | `driver_busy` | accept | у водителя уже есть поездка |
| 422 | `invalid_date_range` | история | `created_from` позже `created_to` |
| 409 | `ride_not_completed` | `cash-received` | поездка ещё не завершена |
| 404 | `payment_not_found` | оплата | при нормальной работе не возникает |
| 403 | `payment_action_forbidden` | `cash-received` | наличные подтверждает только назначенный водитель |
| 409 | `invalid_payment_transition` | `cash-received` | способ не `cash` |
| 503 | `kaspi_unavailable` | `POST /rides` | Kaspi не настроен, только наличные |
| 422 | `validation_error` | любой маршрут | `details.errors[].loc` — поле |
| 404 / 405 | `not_found`, `method_not_allowed` | неизвестный путь или метод | ошибка клиента |
| 500 | `internal_error` | любой маршрут | сообщить с `request_id` |
