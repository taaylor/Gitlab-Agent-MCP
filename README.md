# GitLab Agent MCP

`gitlab-agent-mcp` — локальный MCP-сервер для контролируемой работы AI-агента с
GitLab Merge Requests. Сервер получает MR, diff, discussions и pipelines, публикует
комментарии и suggestions, а также может создать MR после явной команды пользователя.

Сервер не содержит LLM, не читает локальный repository и не изменяет файлы. Анализ кода,
локальные правки, тесты, Git-ветки, commits и `git push` остаются ответственностью Codex
или другого MCP-клиента.

## Возможности

READ tools доступны всегда:

| Tool | Назначение |
|---|---|
| `get_merge_request` | Получить metadata MR |
| `get_merge_request_diff` | Получить unified diff и признаки truncation |
| `get_changed_files` | Получить структурированный список изменённых файлов |
| `get_review_context` | Получить MR, diff, discussions и pipeline одним вызовом |
| `get_mr_discussions` | Получить все discussions |
| `get_unresolved_discussions` | Получить только unresolved discussions |
| `get_discussion` | Получить одну discussion |
| `get_pipeline` | Получить последний или указанный MR pipeline |
| `get_pipeline_jobs` | Получить jobs MR pipeline |
| `get_project_labels` | Получить доступные project и ancestor-group labels |

WRITE tools регистрируются только при `MCP_WRITE_ENABLED=true`:

| Tool | Внешний side effect |
|---|---|
| `create_mr_comment` | Публикует общий комментарий в MR |
| `create_diff_comment` | Публикует inline discussion |
| `create_suggestion` | Публикует настоящий GitLab suggestion |
| `reply_to_discussion` | Отвечает в discussion |
| `resolve_discussion` | Resolve discussion |
| `create_merge_request` | Создаёт Merge Request и возвращает ссылку |

Сервер намеренно не предоставляет `merge`, `approve`, `push`, `force_push`, удаление
веток/проектов, изменение permissions, создание tokens и произвольные GitLab API calls.

## Требования

- Python `3.12`;
- актуальная стабильная версия `uv`;
- GitLab.com или GitLab Self-Managed с REST API v4;
- GitLab access token.

Для READ-only режима достаточно token с правом чтения API. Для публикации комментариев и
создания MR token должен иметь разрешение на соответствующие API write-операции и доступ к
проекту. Используйте минимально необходимые scopes.

## Установка из GitHub через `uv tool`

Замените `taaaylor` на владельца GitHub repository.

Установка последней версии из `main`:

```bash
uv tool install git+https://github.com/taaaylor/gitlab-agent-mcp.git
```

Установка конкретного release tag:

```bash
uv tool install git+https://github.com/taaaylor/gitlab-agent-mcp.git@v0.1.0
```

Установка wheel непосредственно из GitHub Release:

```bash
uv tool install \
  https://github.com/taaaylor/gitlab-agent-mcp/releases/download/v0.1.0/gitlab_agent_mcp-0.1.0-py3-none-any.whl
```

Проверка установки:

```bash
uv tool list
gitlab-agent-mcp --help
```

Принудительное обновление установленного tool из GitHub:

```bash
uv tool install \
  --force \
  git+https://github.com/taaaylor/gitlab-agent-mcp.git@v0.1.0
```

Удаление:

```bash
uv tool uninstall gitlab-agent-mcp
```

Одноразовый запуск без постоянной установки:

```bash
uvx \
  --from git+https://github.com/taaaylor/gitlab-agent-mcp.git@v0.1.0 \
  gitlab-agent-mcp
```

Если package в дальнейшем будет опубликован в PyPI, установка сократится до:

```bash
uv tool install gitlab-agent-mcp
```

GitHub Release уже является поддерживаемым каналом поставки; публикация в PyPI в текущий
release workflow не входит.

## Локальная установка для разработки

```bash
git clone https://github.com/taaaylor/gitlab-agent-mcp.git
cd gitlab-agent-mcp
uv sync --locked --dev
```

Запуск из checkout:

```bash
uv run --no-sync gitlab-agent-mcp
```

## Конфигурация

Все настройки передаются через environment variables:

| Переменная | Обязательность | Default | Описание |
|---|---:|---:|---|
| `GITLAB_URL` | да | — | Origin GitLab, например `https://gitlab.example.com` |
| `GITLAB_TOKEN` | да | — | Access token; никогда не храните его в Git |
| `MCP_WRITE_ENABLED` | нет | `false` | Регистрировать ли WRITE tools |
| `GITLAB_TIMEOUT_SECONDS` | нет | `30` | Общий timeout одного HTTP-запроса |
| `GITLAB_MAX_PAGES` | нет | `100` | Защита от неограниченной pagination |
| `GITLAB_READ_RETRIES` | нет | `2` | Число повторов безопасных READ-запросов |
| `GITLAB_CA_BUNDLE` | нет | — | PEM CA bundle для Self-Managed GitLab |

Пример READ-only запуска:

```bash
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="<TOKEN>"
export MCP_WRITE_ENABLED="false"

gitlab-agent-mcp
```

Включение WRITE tools:

```bash
export MCP_WRITE_ENABLED="true"
gitlab-agent-mcp
```

Не добавляйте реальный token в `.env.example`, Git, README, shell scripts или логи.
Локальный `.env` поддерживается, но исключён через `.gitignore`.

## Подключение к Codex

После установки через `uv tool` экспортируйте настройки в environment и зарегистрируйте
stdio-сервер:

```bash
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="<TOKEN>"
export MCP_WRITE_ENABLED="false"

codex mcp add gitlab-agent-mcp -- gitlab-agent-mcp
```

Запускайте Codex из environment, где доступны эти переменные. Команда соответствует текущему
stdio-формату `codex mcp add`: после `--` указывается executable MCP-сервера. Не передавайте
token в command line на общей машине — он может сохраниться в shell history.

Для WRITE-режима измените environment перед запуском Codex:

```bash
export MCP_WRITE_ENABLED="true"
codex
```

WRITE tools содержат предупреждение о внешнем side effect. Наличие tool не означает разрешение
использовать его без подтверждения пользователя.

## Подключение к другому MCP-клиенту

Для любого клиента с поддержкой stdio используются следующие параметры:

```json
{
  "command": "gitlab-agent-mcp",
  "args": [],
  "env": {
    "GITLAB_URL": "https://gitlab.example.com",
    "GITLAB_TOKEN": "<TOKEN>",
    "MCP_WRITE_ENABLED": "false"
  }
}
```

Формат файла конфигурации и способ безопасного хранения secrets зависят от конкретного клиента.

## Примеры READ-only использования

Получить MR:

```text
Покажи состояние MR:
https://gitlab.example.com/platform/backend/-/merge_requests/142
```

Посмотреть замечания:

```text
Получи unresolved discussions из MR 142 и скажи,
с какими замечаниями ты согласен. Ничего не публикуй.
```

Исправить замечания локально:

```text
Исправь обоснованные замечания из этого MR.
Измени локальный код, добавь тесты и запусти проверки.
Не отвечай в GitLab и не resolve discussions.
```

Провести code review без публикации:

```text
Сделай review этого MR. Ищи correctness, authorization,
transactions, concurrency, N+1, compatibility и недостающие тесты.
Сначала покажи результат мне. Ничего в GitLab не публикуй.
```

Проверить pipeline:

```text
Покажи последний pipeline этого MR и все failed jobs.
```

Посмотреть labels проекта:

```text
Покажи доступные labels feature, bugfix и chore в проекте:
https://gitlab.example.com/platform/backend
```

## Примеры WRITE-операций review

WRITE tools доступны только при `MCP_WRITE_ENABLED=true`.

Опубликовать выбранные замечания:

```text
Опубликуй замечания 1 и 3 как inline comments.
Замечание 2 не публикуй.
```

Создать suggestion:

```text
Для замечания 3 создай GitLab suggestion с предложенной заменой.
```

Ответить после исправления:

```text
Ответь в исправленных discussions, кратко опиши изменения.
Пока не resolve их.
```

Resolve только после отдельной команды:

```text
Resolve discussions 7f43a1 и 812bcd: исправления уже проверены.
```

## Создание Merge Request

MR создаётся только после прямой команды пользователя, например:

```text
Создай MR на GitLab для задачи PROJ-123.
Тип задачи feature, описание — добавить экспорт отчёта в CSV.
```

Фразы «исправь задачу», «покажи diff», «запусти тесты», «сделай commit» или «проведи review»
не являются разрешением создать MR.

### GitFlow naming

Разрешены ветки:

```text
feature/<Номер задачи>
bugfix/<Номер задачи>
chore/<Номер задачи>
```

Примеры:

```text
feature/PROJ-123
bugfix/456
chore/DEVOPS-78
```

Commit message:

```text
<feature|bugfix|chore>: <Описание задачи> (<Номер задачи>)
```

Примеры:

```text
feature: Добавить экспорт отчёта в CSV (PROJ-123)
bugfix: Исправить повторную отправку уведомлений (456)
chore: Обновить конфигурацию линтера (DEVOPS-78)
```

Символ `|` обозначает выбор одного типа и не включается в commit message.

### Полный сценарий

```text
1. Codex проверяет git status и связанные изменения.
2. Codex создаёт или проверяет ветку feature/PROJ-123.
3. Codex запускает tests, lint и type check проекта.
4. Codex создаёт commit:
   feature: Добавить экспорт отчёта в CSV (PROJ-123)
5. Codex выполняет git push после явного запроса пользователя.
6. MCP проверяет существование remote source и target branches.
7. MCP проверяет, нет ли уже открытого MR для этой пары веток.
8. MCP получает labels и назначает существующий label feature.
9. MCP создаёт MR.
10. MCP возвращает web_url, а агент показывает ссылку в чате.
```

MCP не создаёт label. Если `feature`, `bugfix` или `chore` отсутствует, MR создаётся без label
и в результате возвращается предупреждение.

Если открытый MR с той же source/target branch уже существует, новый MR не создаётся, а сервер
возвращает ссылку на существующий.

### Ссылка на созданный MR

`create_merge_request` всегда возвращает ссылку в трёх местах:

```json
{
  "created": true,
  "web_url": "https://gitlab.example.com/platform/backend/-/merge_requests/142",
  "message": "Merge Request создан: https://gitlab.example.com/platform/backend/-/merge_requests/142",
  "merge_request": {
    "iid": 142,
    "web_url": "https://gitlab.example.com/platform/backend/-/merge_requests/142"
  }
}
```

Описание MCP tool отдельно требует от агента показать `web_url` пользователю как кликабельную
ссылку. Ожидаемый ответ в чате:

```text
Merge Request создан: https://gitlab.example.com/platform/backend/-/merge_requests/142
```

## Inline positions

GitLab различает стороны diff:

- добавленная строка: только `new_line`;
- удалённая строка: только `old_line`;
- неизменённая context-строка: одновременно `old_line` и `new_line`.

Перед публикацией сервер получает latest diff refs и проверяет, что указанная позиция реально
присутствует в последнем diff. Для `collapsed` и `too_large` файлов inline comment отклоняется,
а не создаётся на потенциально неверной строке.

## Безопасность HTTP

- GitLab URL обязан иметь тот же origin, что и `GITLAB_URL`;
- token никогда не отправляется на host из произвольного `mr_url`;
- redirects отключены;
- TLS verification включена;
- custom CA подключается через `GITLAB_CA_BUNDLE`;
- pagination ограничена;
- READ-запросы повторяются только для transport errors, rate limit и временных server errors;
- WRITE-запросы не повторяются автоматически;
- HTTP statuses представлены через `http.HTTPStatus`, без числовых status literals;
- группы HTTP ошибок обрабатываются через `match/case`.

## Архитектура

```text
src/gitlab_agent_mcp/
├── domain/          # entities, enums, exceptions, repository Protocol
├── application/     # use cases, validation, JSON-safe DTO conversion
├── infrastructure/  # settings, URL parser, aiohttp client, GitLab repository
├── presentation/    # FastMCP server and tool registration
└── main.py          # CLI composition and stdio startup
```

`GitLabApiRepository` не содержит публичного произвольного `request(path)` API. Каждый разрешённый
GitLab endpoint представлен отдельным методом.

## Разработка и проверки

```bash
uv lock
uv sync --locked --dev

uv run --no-sync ruff format .
uv run --no-sync ruff check .
uv run --no-sync mypy src
uv run --no-sync pytest -m "not integration"

uv build
```

Integration tests должны запускаться только против отдельного тестового GitLab:

```bash
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="<TEST_TOKEN>"
export GITLAB_INTEGRATION_PROJECT_URL="https://gitlab.example.com/sandbox/test-project"

uv run --no-sync pytest -m integration
```

## Release

Версия хранится только в `[project].version` файла `pyproject.toml`. Push в `main` запускает
полный build pipeline и создаёт GitHub Release `vX.Y.Z`, если такого release ещё нет. Pull Request
в `main` выполняет проверки и сборку, но release не создаёт.

Release содержит:

```text
gitlab_agent_mcp-X.Y.Z-py3-none-any.whl
gitlab_agent_mcp-X.Y.Z.tar.gz
gitlab-agent.env.example
README.md
SHA256SUMS
```

Перед новым release необходимо увеличить версию по Semantic Versioning.
