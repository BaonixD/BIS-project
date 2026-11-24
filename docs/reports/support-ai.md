# ИИ-помощник поддержки (Gemini) — реализация и включение

23 ноября 2026. План: [gemini-support-faq](../plans/gemini-support-faq.md). Ветка
`feature/support-ai` от `559ba1c`.

## Решения владельца (опрос перед реализацией)

- Цены: помощник называет ставки `edu-v2` и минимум, точную сумму — «в приложении до заказа».
- ИИ отвечает во всех категориях обращений; по конкретным поездкам/оплатам сам зовёт оператора.
- Угроза безопасности: сначала 112 (102/103), затем «Позвать оператора».
- Учебный характер упоминается только для Kaspi (имитация оплаты).
- Автотесты по указанию владельца не писались; проверены существующие наборы и реальный API.

## Результат

- Настройки `SupportAISettings` (`SUPPORT_AI_ENABLED`, `GEMINI_*`, `LLM_*`), ключ `SecretStr`.
- Промпт и справка — `modules/support/ai_knowledge.py`; язык ответа определяется в коде
  (латиница → en, казахские буквы → kk, иначе ru) и передаётся модели явно.
- `GeminiProvider` на `httpx`: `x-goog-api-key`, `thinkingBudget=0` для 2.5-flash,
  `asyncio.timeout`; блокировка, `MAX_TOKENS`, пустой ответ и >2000 символов — `failed`.
- Миграция `313456def5e5`: `author_kind`, nullable `author_id` с CHECK, `ai_reply_to_seq`
  с UNIQUE; `support_mode`, `ai_state`, `ai_source_seq`, `ai_started_at`. Downgrade удаляет
  ответы ИИ и возвращает схему.
- LEFT JOIN сообщений, unread учитывает `author_id IS NULL`; `TicketView.ai_available`.
- `POST /support/tickets/{id}/handoff` (владелец/admin, CSRF, идемпотентно, чужое — 404).
- Фоновый `SupportAILoop`: условные UPDATE по `ai_source_seq`, сеть вне транзакций,
  очередь ≤ 20, `running` → `failed` при старте. Один worker Uvicorn.
- Frontend: плашка «ИИ-помощник», «Позвать оператора»/«Подключиться» для admin, статусы
  ожидания/сбоя (`role=status`, reduced motion), подпись сообщений ИИ, пометка о Gemini
  в форме нового обращения, RU/KK/EN.

## Проверки

- `scripts/lint.py`, `mypy` — чисто. Frontend: lint, typecheck, 191 тест, build — успешно.
- `pytest`: 1875 passed, 13 failed. Все 13 воспроизводятся на `main` без этих изменений:
  12 — `NotImplementedError` в downgrade `8a0ee43fd0b2`, 1 — `test_routing_wiring` читает
  локальный `.env` с настройками маршрутизации.
- Миграция: upgrade/downgrade/upgrade на копии `local.db` (backup API), `alembic check`
  без расхождений. Локальная БД обновлена, копия — `local.before-support-ai-20261123.db`.
- Реальный Gemini (`gemini-2.5-flash`, ключ владельца): FAQ RU/KK/EN, вопрос вне справки,
  «проверь мою поездку», смена роли/раскрытие промпта, угроза безопасности. Найдено и
  исправлено: английский вопрос получал русский ответ; модель пересказывала инструкции;
  порядок шагов Kaspi уточнён. Ответы 1–10 с, единичный 26 с.
- E2E на копии БД, порт 8100: создание → `pending` → ответ ИИ (~1,2 с), unread=1, повтор
  создания/сообщения без дубля ответа, продолжение диалога, handoff ×2, после handoff ИИ
  молчит, неверный CSRF — 403, чужой handoff — 404. В логе нет ключа и текста переписки.

## Не проверено

- Визуально на 360/390 px и desktop в браузере.
- Гонки «медленная генерация + ответ admin/новое сообщение» и перезапуск с `running`
  проверены чтением кода (условные UPDATE), не автотестом.

## Включение и отключение

Локально: `SUPPORT_AI_ENABLED=true` в `.env`, старый `LLM_SYSTEM_PROMPT` закомментирован
(используется встроенный промпт). Отключение: `SUPPORT_AI_ENABLED=false` и рестарт API.
