# ARGUS Brief Agent MVP

Локальный MVP для загрузки CSV-каталога цен с готовыми embeddings, индексации в Qdrant, сбора брифа и простого семантического поиска в ARGUS-style чате.

## Требования

- Python 3.11+
- uv для управления Python-зависимостями
- Node.js 20+
- Docker для локального PostgreSQL и Qdrant
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

### 2. Поднимите PostgreSQL и Qdrant

```bash
make db
make qdrant
```

Локальная авторизация хранит пользователей и bearer-сессии в PostgreSQL. Таблицы `auth_users` и `auth_sessions` создаются backend автоматически при первой регистрации, логине, проверке токена или seed-admin запуске.

### 3. Создайте dev-admin пользователя

Для локальной разработки и тестов можно создать пользователя с ролью `admin`. Заполните в `.env`:

```bash
DATABASE_URL=postgresql://argus:argus@127.0.0.1:5432/argus
DEV_ADMIN_EMAIL=developer@example.com
DEV_ADMIN_PASSWORD=надежный-пароль-для-разработки
DEV_ADMIN_ROLE=admin
```

Затем выполните:

```bash
make seed-admin
```

Команда создаёт локального пользователя в PostgreSQL. Если пользователь уже существует с тем же паролем, команда завершится успешно и вернёт существующего пользователя.

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

### 5. Запустите backend и frontend

```bash
make backend
```

```bash
make frontend
```

Откройте `http://localhost:5173`. Приложение сначала попросит войти или зарегистрироваться через локальную email/password авторизацию. После входа загрузите CSV-файл, например `data/prices.csv`, дождитесь статуса `ready` и используйте режим `Планирование брифа` или `Семантический поиск`.

Готовые сценарии для показа лежат в [`DEMO_GUIDE.md`](DEMO_GUIDE.md).

### Запуск одной командой

После настройки `.env` и установки зависимостей можно запустить PostgreSQL, Qdrant, backend и frontend одной командой:

```bash
make dev
```

`make dev` запускает PostgreSQL и Qdrant через Docker Compose, затем параллельно стартует FastAPI и Vite. Остановить foreground-процессы можно через `Ctrl+C`, контейнеры останавливаются командой:

```bash
make db-down
```

## Ручной Запуск

Создайте `.env`, поднимите локальные сервисы и установите backend-зависимости:

```bash
cp .env.example .env
docker compose up -d postgres qdrant
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

### Local PostgreSQL Auth

- `DATABASE_URL` - локальный Postgres URL для пользователей и bearer-сессий.
- `AUTH_SESSION_TTL_SECONDS` - время жизни access token в секундах. По умолчанию 7 дней.

### Dev/test admin seed

- `DEV_ADMIN_EMAIL` - email пользователя разработчика.
- `DEV_ADMIN_PASSWORD` - пароль пользователя разработчика.
- `DEV_ADMIN_ROLE` - роль, записываемая в `app_metadata.role`; по умолчанию `admin`.

### Proxy bypass for local containers

- `NO_PROXY` / `no_proxy` - список локальных адресов, которые не должны уходить в системный proxy. В `.env.example` уже добавлены `localhost`, `127.0.0.1`, `::1`, `0.0.0.0`, `host.docker.internal`.

Makefile дополнительно прокидывает этот bypass в `make backend`, `make seed-admin` и локальные проверки сервисов. Это нужно, если в системе включён HTTP/HTTPS proxy: без bypass запросы к локальным Docker-портам Qdrant и backend могут уходить в proxy и возвращать `503`, `Connection refused` или странные upstream-ошибки.

Если запросы из браузера к `http://localhost:8000` тоже ломаются, добавьте локальные адреса в bypass системного proxy macOS/browser:

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
