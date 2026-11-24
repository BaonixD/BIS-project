# Деплой TulparTaxi в Dokploy

Один сервис (Application) из этого репозитория: `Dockerfile` собирает фронтенд и бэкенд в один
образ, данные (SQLite и документы водителей) — на постоянном томе. Почему так — [ADR 0017](decisions/0017-deploy-dokploy.md).

## 1. Создать приложение

1. **Projects → pet projects → Create Service → Application**, имя `tulpartaxi`.
2. **General → Provider: GitHub**, репозиторий `BaonixD/BIS-project`, ветка `main`
   (если GitHub не подключён: Settings → Git → GitHub App).
3. **Build Type: Dockerfile**, путь `Dockerfile`, контекст — корень репозитория.

## 2. Переменные окружения (Environment)

Обязательные (`<домен>` — например `taxi.baonix.su`):

```dotenv
CORS_ALLOWED_ORIGINS=https://<домен>
ROUTING_PROVIDER=mapbox
MAPBOX_TOKEN=<токен Mapbox>
```

По желанию:

```dotenv
KASPI_PAYMENT_URL=https://pay.kaspi.kz/pay/<id>   # без неё Kaspi скрыт, работают наличные
SUPPORT_AI_ENABLED=true                           # ИИ-помощник в поддержке
GEMINI_API_KEY=<ключ>
GOOGLE_CLIENT_ID=<id>                             # вход через Google; домен добавить в Google Console
LOG_LEVEL=INFO
```

Уже заданы в образе (менять не нужно): `DATABASE_URL=sqlite+aiosqlite:////data/tulpar.db`,
`DOCUMENT_STORAGE_DIR=/data/driver-documents`, `SESSION_COOKIE_SECURE=true`,
`FRONTEND_DIST=/app/frontend/dist`. Секреты храните только в Dokploy, не в Git.

## 3. Том для данных (Advanced → Volumes / Mounts)

**Volume Mount**: имя `tulpartaxi-data`, путь в контейнере `/data`.
Без тома база и документы пропадут при каждом новом деплое.

## 4. Домен (Domains)

**Add Domain**: хост `<домен>`, путь `/`, **Container Port `8000`**, HTTPS включён,
сертификат **Let's Encrypt**. DNS: A-запись домена на IP сервера Dokploy.

## 5. Deploy

Нажать **Deploy** и дождаться в логах `Application started`. Проверка:
`https://<домен>/health/ready` → `{"status":"ready"}`, `https://<домен>/` — экран входа.

## 6. Первый админ и демо-данные (один раз)

В Dokploy: приложение → **Docker → Terminal** (или `docker exec -it <контейнер> sh` на сервере):

```sh
ADMIN_PASSWORD='<пароль от 10 символов>' python scripts/create_admin.py --username admin
DEMO_PASSWORD='<пароль для демо>' python scripts/seed.py      # пассажиры, водители, документы
```

Демо-водители получают свежие координаты на 60 секунд; перед показом —
`DEMO_PASSWORD=... python scripts/seed.py --refresh-locations` или выйти водителем на линию в приложении.

## 7. Обновление

Пуш в `main` → **Deploy** (или включить Auto Deploy в Dokploy). Миграции применяются сами при
старте. Пользователи установленного приложения увидят «Доступна новая версия · Обновить».

## 8. Резервная копия

SQLite нельзя копировать «на ходу» обычным `cp` (WAL). В терминале контейнера:

```sh
python -c "import sqlite3; s=sqlite3.connect('/data/tulpar.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close()"
```

Затем скачать `/data/backup.db` и папку `/data/driver-documents`. Либо настроить
Volume Backups в Dokploy (если есть в вашей версии) на том `tulpartaxi-data`.

## Ограничения

- Один контейнер и один worker: масштабировать репликами нельзя (SQLite и фоновые циклы).
  Для учебного проекта этого достаточно.
- Поиск адресов идёт из браузера в публичный Nominatim (1 запрос в секунду с устройства).
- Своего OSRM на сервере нет: маршруты строит Mapbox.
