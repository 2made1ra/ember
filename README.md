# ARGUS Brief Agent MVP

Локальный MVP для загрузки CSV-каталога цен с готовыми embeddings, индексации в Qdrant, сбора брифа и простого семантического поиска в ARGUS-style чате.

## Требования

- Python 3.11+
- uv для управления Python-зависимостями
- Node.js 20+
- Docker для локального Qdrant и локального Supabase
- Supabase CLI для локального Supabase stack
- OpenAI-compatible chat API
- OpenAI-compatible embedding API

По умолчанию проект настроен на внешний OpenAI-compatible API:

- `CHAT_BASE_URL=https://api.vsellm.ru/v1`
- `CHAT_MODEL=openai/gpt-oss-120b`
- `EMBEDDING_BASE_URL=https://api.vsellm.ru/v1`
- `EMBEDDING_MODEL=openai/text-embedding-3-small`

Для локального fallback можно использовать LM Studio через `LM_STUDIO_BASE_URL`.

## Быстрый Запуск

### 1. Подготовьте окружение

```bash
make env
make install
```

`make env` создаёт `.env` из `.env.example`, если файла ещё нет. После этого заполните `.env` реальными ключами и адресами.

### 2. Поднимите локальный Supabase Auth

Проект рассчитан на локальный Supabase Auth через Supabase CLI. CLI добавлен как root dev dependency и устанавливается командой `make install`; Makefile запускает его через `npx supabase`.

Локальная конфигурация хранится в `supabase/config.toml`. Она настроена на Vite frontend `http://localhost:5173` и локальные Supabase порты по умолчанию. Для минимального локального Auth-стека включены только необходимые контейнеры: Postgres, Auth и Kong gateway. Realtime, Storage, Studio, Edge Runtime, Analytics, PostgREST, Inbucket/Mailpit и прочие дополнительные сервисы не запускаются.

Если конфигурацию нужно пересоздать:

```bash
make supabase-init
```

Запустите локальный Supabase Auth stack:

```bash
make supabase-start
```

Email/Password provider в локальном Auth stack включён в стандартной конфигурации. Supabase Studio в минимальном запуске отключена.

Посмотрите локальные URL и ключи:

```bash
make supabase-status
```

В выводе нужны `API URL`, клиентский ключ и секретный admin key. В разных версиях CLI они могут называться `Publishable` / `Secret` или `anon key` / `service_role key`. В стандартном локальном запуске `API URL` равен `http://127.0.0.1:54321`.

В `.env` заполните backend-переменные для проверки access token:

```bash
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_PUBLISHABLE_KEY=локальный-Publishable-или-anon-key-из-supabase-status
```

Заполните frontend-переменные для browser client:

```bash
VITE_SUPABASE_URL=http://127.0.0.1:54321
VITE_SUPABASE_PUBLISHABLE_KEY=локальный-Publishable-или-anon-key-из-supabase-status
```

`SUPABASE_PUBLISHABLE_KEY` и `VITE_SUPABASE_PUBLISHABLE_KEY` обычно имеют одинаковое значение. Разные имена нужны потому, что Vite отдаёт в браузер только переменные с префиксом `VITE_`.

### 3. Создайте dev-admin пользователя

Для локальной разработки и тестов можно создать пользователя с ролью `admin`. Заполните в `.env`:

```bash
SUPABASE_SERVICE_ROLE_KEY=локальный-Secret-или-service_role-key-из-supabase-status
DEV_ADMIN_EMAIL=developer@example.com
DEV_ADMIN_PASSWORD=надежный-пароль-для-разработки
DEV_ADMIN_ROLE=admin
```

Затем выполните:

```bash
make seed-admin
```

Команда создаёт Supabase Auth пользователя, подтверждает email и записывает роль в `app_metadata.role`.

`SUPABASE_SERVICE_ROLE_KEY` даёт административный доступ к Supabase. Храните его только в server-side `.env`, не добавляйте в frontend, не называйте с префиксом `VITE_` и не публикуйте.

### 4. Настройте AI API

Минимальная конфигурация для chat и embeddings:

```bash
API_KEY=ваш-ключ
CHAT_BASE_URL=https://api.vsellm.ru/v1
CHAT_MODEL=openai/gpt-oss-120b
EMBEDDING_BASE_URL=https://api.vsellm.ru/v1
EMBEDDING_MODEL=openai/text-embedding-3-small
```

`CHAT_API_KEY` можно оставить пустым. Тогда chat model использует `API_KEY`. Если для chat нужен отдельный ключ:

```bash
CHAT_API_KEY=ваш-chat-ключ
```

### 5. Запустите сервисы

Если Supabase уже запущен, поднимите Qdrant:

```bash
make qdrant
```

Запустите backend и frontend в двух терминалах:

```bash
make backend
```

```bash
make frontend
```

Откройте `http://localhost:5173`. Приложение сначала попросит войти или зарегистрироваться через Supabase email/password. После входа загрузите CSV-файл, например `data/prices.csv`, дождитесь статуса `ready` и используйте режим `Планирование брифа` или `Семантический поиск`.

Готовые сценарии для показа лежат в [`DEMO_GUIDE.md`](DEMO_GUIDE.md).

### Запуск одной командой

После настройки `.env` и установки зависимостей можно запустить локальный Supabase, Qdrant, backend и frontend одной командой:

```bash
make dev
```

`make dev` запускает минимальный Supabase Auth stack, Qdrant через Docker Compose, затем параллельно стартует FastAPI и Vite. Остановить foreground-процессы можно через `Ctrl+C`, Qdrant отдельно останавливается командой:

```bash
make qdrant-down
```

Локальный Supabase останавливается отдельно:

```bash
make supabase-stop
```

## Ручной Запуск

Создайте `.env`, поднимите локальные сервисы и установите backend-зависимости:

```bash
cp .env.example .env
npx supabase init
npx supabase start --exclude realtime,storage-api,imgproxy,mailpit,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor
npx supabase status
docker compose up -d qdrant
uv sync --project backend
```

Запустите backend:

```bash
uv run --project backend uvicorn app.main:app --app-dir backend --env-file .env --reload
```

В другом терминале установите frontend-зависимости и запустите Vite:

```bash
cd frontend
npm install
npm run dev
```

Для ручного создания dev-admin пользователя без Makefile:

```bash
set -a
. ./.env
set +a
PYTHONPATH=backend UV_CACHE_DIR=.uv-cache uv run --project backend python -m app.dev_admin
```

## Переменные Окружения

### Local OpenAI-compatible fallback

- `LM_STUDIO_BASE_URL` - адрес локального OpenAI-compatible сервера, обычно LM Studio.
- `LM_STUDIO_CHAT_MODEL` - имя локальной chat model.

### Shared AI API key

- `API_KEY` - общий ключ для chat и embeddings, если отдельные ключи не заданы.

### Chat model

- `CHAT_BASE_URL` - OpenAI-compatible endpoint для генерации ответов.
- `CHAT_MODEL` - chat model.
- `CHAT_API_KEY` - отдельный ключ для chat; если пустой, используется `API_KEY`.

### Embedding model

- `EMBEDDING_BASE_URL` - OpenAI-compatible endpoint для embeddings.
- `EMBEDDING_MODEL` - embedding model.

### Vector store

- `QDRANT_URL` - адрес Qdrant.
- `QDRANT_COLLECTION` - коллекция с каталогом цен.

### Local Supabase Auth

- `SUPABASE_URL` - локальный Supabase API URL для backend, обычно `http://127.0.0.1:54321`.
- `SUPABASE_PUBLISHABLE_KEY` - локальный клиентский ключ из `supabase status`: `Publishable` или `anon key`, в зависимости от версии CLI.
- `VITE_SUPABASE_URL` - URL локального Supabase для frontend.
- `VITE_SUPABASE_PUBLISHABLE_KEY` - тот же локальный клиентский ключ, но доступный Vite/browser client.

### Dev/test admin seed

- `SUPABASE_SERVICE_ROLE_KEY` - локальный секретный admin key для Supabase Admin API: `Secret` или `service_role key`. Только server-side.
- `DEV_ADMIN_EMAIL` - email пользователя разработчика.
- `DEV_ADMIN_PASSWORD` - пароль пользователя разработчика.
- `DEV_ADMIN_ROLE` - роль, записываемая в `app_metadata.role`; по умолчанию `admin`.

### Local Supabase SQL

- `SUPABASE_DB_URL` - локальный Postgres URL из `supabase status`. Сейчас зарезервирован для будущих SQL-возможностей.

### Proxy bypass for local containers

- `NO_PROXY` / `no_proxy` - список локальных адресов, которые не должны уходить в системный proxy. В `.env.example` уже добавлены `localhost`, `127.0.0.1`, `::1`, `0.0.0.0`, `host.docker.internal`.

Makefile дополнительно прокидывает этот bypass в `make backend`, `make seed-admin`, `make supabase-status`, `make supabase-start`, `make supabase-stop` и локальные проверки сервисов. Это нужно, если в системе включён HTTP/HTTPS proxy: без bypass запросы к локальным Docker-портам Supabase и Qdrant могут уходить в proxy и возвращать `503`, `Connection refused` или странные upstream-ошибки.

Если запросы из браузера к `http://127.0.0.1:54321` или `http://localhost:8000` тоже ломаются, добавьте локальные адреса в bypass системного proxy macOS/browser:

```text
localhost, 127.0.0.1, ::1, 0.0.0.0
```

Перезапустите backend и frontend после изменения proxy-настроек.

## Проверки

Через Makefile:

```bash
make test
make build
```

Или вручную:

```bash
uv run --project backend python -m unittest discover -s backend/tests -t backend -v

cd frontend
npm test
npm run build
```

## Поведение MVP

- Поддерживается один активный каталог.
- Каждая новая загрузка CSV пересоздаёт коллекцию Qdrant и сбрасывает состояние брифа.
- Колонка `embedding` из CSV используется как готовый вектор каталога.
- Текст для embedding строится строго как `{name} {unit} {category} {section} {supplier}`.
- Режим `Семантический поиск` отправляет в embedding-модель голый текст запроса, забирает top-20 кандидатов из Qdrant, переранжирует их по совпадениям слов в `name`, `category`, `section`, `source_text`, `supplier` и пропускает итоговый top-3 через небольшой LangGraph-агент. В чат выводится человекочитаемый список по payload-полям каталога: название, цена, единица, поставщик, город, категория, раздел и ID. Внутренний score не показывается.
- Режим `Планирование брифа` работает как управляемый LangGraph workflow: сначала собирает тип события, город, количество гостей и бюджет, затем определяет нужные блоки услуг и только после этого ищет подрядчиков в Qdrant.
- При ingest backend добавляет в Qdrant payload производные поля для брифа: `service_type`, `city_normalized`, `supplier_status_normalized`, `unit_kind`, `quantity_kind`. Они используются для фильтров и расчёта сметы без SQL-базы.
- Поиск внутри бриф-агента делает semantic top-20, фильтрует по `service_type`, городу и активному статусу поставщика, затем возвращает top-3 кандидата на каждый блок услуг.
- Если пользователь пишет общий запрос вроде “хочу организовать мероприятие”, агент не ищет подрядчиков сразу, а задаёт до 4 уточняющих вопросов.
- Цены берутся только из каталога. Агент не должен придумывать цены.

## Диагностика загрузки CSV

Если на загрузке видно `Connection refused`, значит один из сервисов не запущен, недоступен по сети или слушает другой адрес.

Проверьте:

```bash
make check-services
```

Ожидаемо:

- FastAPI отвечает на `http://localhost:8000/api/health`
- LM Studio отвечает на `${LM_STUDIO_BASE_URL}/models` из `.env`, если используете локальный chat fallback
- Embedding API отвечает на `${EMBEDDING_BASE_URL}/models` с `API_KEY`
- Chat API отвечает на `${CHAT_BASE_URL}/models` с `CHAT_API_KEY` или `API_KEY`
- Qdrant отвечает на `${QDRANT_URL}/readyz` из `.env`

Для embeddings из текущего `data/prices.csv` backend не пересчитывает строки каталога: он читает готовую колонку `embedding`. Embedding API нужен для пользовательского поискового запроса и для поиска внутри бриф-агента. Минимальная конфигурация:

```bash
API_KEY=ваш-ключ
EMBEDDING_BASE_URL=https://api.vsellm.ru/v1
EMBEDDING_MODEL=openai/text-embedding-3-small
CHAT_BASE_URL=https://api.vsellm.ru/v1
CHAT_MODEL=openai/gpt-oss-120b
```

`CHAT_API_KEY` можно не задавать, тогда для генерации брифа используется `API_KEY`. Если для chat нужен отдельный ключ:

```bash
CHAT_API_KEY=ваш-chat-ключ
```

Если хотите вернуть LM Studio для chat model на другой машине в локальной сети, укажите полный адрес в `.env`, например:

```bash
LM_STUDIO_BASE_URL=http://192.168.1.44:1234/v1
CHAT_BASE_URL=http://192.168.1.44:1234/v1
CHAT_MODEL=имя-загруженной-chat-модели
```

После изменения `.env` перезапустите backend.
