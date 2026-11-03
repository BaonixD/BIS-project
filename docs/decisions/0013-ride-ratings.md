# 0013. Оценки после поездки

Статус: принято владельцем 3 ноября 2026 года (макет Figma). Раньше рейтинги были вне объёма MVP_SPEC §2.

## Контекст

В макете после завершения пассажир ставит водителю звёзды и теги, водитель — пассажиру; средний рейтинг виден в карточке водителя и в предложении водителю.

## Решение

**Хранение.** `ride_ratings`: `id`, `ride_id` → `rides`, `rater_id` и `ratee_id` → `users`, `rater_role` (`passenger|driver`), `stars`, `comment` (≤ 500, nullable), `created_at`. Ограничения: CHECK `stars BETWEEN 1 AND 5`, перечень `rater_role`, `comment IS NULL OR length(comment) BETWEEN 1 AND 500`, `rater_id <> ratee_id`, `UNIQUE (ride_id, rater_role)` — одна оценка каждой стороны. Индекс `(ratee_id, stars)` для средних.

**Теги** — отдельная таблица `ride_rating_tags (rating_id → ride_ratings ON DELETE CASCADE, tag)`, `PRIMARY KEY (rating_id, tag)`, CHECK перечня всех тегов. Выбрана вместо строки через запятую: БД сама проверяет каждое значение и отсутствие повторов, таблица переносима на PostgreSQL без массивов. Какие теги разрешены стороне, проверяет Python (CHECK не знает `rater_role` родителя). Ответы перечисляют теги в фиксированном порядке стороны, повторы в запросе отбрасываются.

| Кто оценивает | Кого | Теги |
| --- | --- | --- |
| пассажир поездки | водителя | `polite`, `clean_car`, `smooth_driving`, `knows_route` |
| назначенный водитель | пассажира | `on_time`, `polite`, `clean` |

**API.** `POST /api/v1/rides/{ride_id}/rating {"stars": 1..5, "tags": [...], "comment": str | null}` → `201 {ride_id, rater_role, stars, tags, comment, created_at}`. `stars` — строго целое; `tags` по умолчанию `[]`; `comment` обрезается, пустой — `null`, управляющие символы кроме `\n` и `\t` — 422. Одна пишущая транзакция, поездка блокируется первой (`rides → ride_ratings`). Порядок проверок:

1. поездки нет или пользователь её не видит — `404 ride_not_found`;
2. видит, но не участник (admin) — `403 rating_forbidden`;
3. тег чужой стороны — `422 validation_error` (`loc: ["body", "tags", i]`, `type: rating_tag_not_allowed`); неизвестный тег, `stars` вне 1–5, лишнее поле — обычная `422`;
4. поездка не `completed` — `409 ride_not_completed`;
5. эта сторона уже оценила — `409 rating_already_exists` (и при проигранной гонке: нарушение `UNIQUE` переводится в тот же ответ).

Оценку нельзя изменить или удалить.

**Чтение.** `GET /rides/{ride_id}` содержит `my_rating: {stars, tags, comment} | null` — оценку запрашивающего (у admin всегда `null`). Средний рейтинг `{"average": float | null, "count": int}` (среднее по полученным оценкам, два знака; без оценок — `null`/`0`): `driver.rating` в карточке водителя поездки, `rating` в `DriverResponse` (`/drivers/me` и admin-список), `passenger_rating` в `OfferResponse`, `rating` в `GET /users/me`. Списки (предложения, admin-список водителей) получают рейтинги одним сгруппированным запросом на страницу, без N+1.

**Миграция `d9f6c93e85a9`** создаёт обе таблицы; откат удаляет их вместе с оценками.

## Последствия

- Средний рейтинг считается при каждом чтении (`AVG` по индексу); денормализации и кэша нет — для учебных объёмов достаточно.
- Оценка не влияет на dispatch и допуск водителя.
