# Promotion Plan for mcp-superset

## 1. awesome-mcp-servers PR (82.7k stars)

**PR создан:** https://github.com/punkpeye/awesome-mcp-servers/pull/3039

Запись добавлена в секцию **"📊 Data Platforms"** (алфавитный порядок, между `aywengo/kafka-schema-reg-mcp` и `bruno-portfolio/agrobr-mcp`).

---

## 2. Smithery.ai

Файл `smithery.yaml` уже создан в корне mcp-superset/.

**Действия:**
1. Перейти на https://smithery.ai → Login через GitHub
2. Зарегистрировать сервер: https://smithery.ai/new → указать GitHub repo `bintocher/mcp-superset`
3. Smithery автоматически подтянет smithery.yaml и опубликует сервер
4. После публикации — добавить Smithery badge в README.md

---

## 3. mcp.so

**URL подачи:** https://mcp.so/submit

**Действия:**
1. Перейти на https://mcp.so/submit
2. Тип: MCP Server
3. Name: `mcp-superset`
4. URL: `https://github.com/bintocher/mcp-superset`
5. Description: Full-featured MCP server for Apache Superset — 135+ tools for dashboards, charts, datasets, SQL Lab, security (users, roles, RLS, groups), audit, and more. Built-in safety validations.
6. Submit и ожидать модерации

> **Примечание:** На mcp.so уже есть запись `superset-mcp` от `@aptro` (конкурент). Наша — отдельная.

---

## 4. Glama.ai

**Два пути:**

### Путь A — Official MCP Registry (рекомендуется)

Glama и PulseMCP автоматически индексируют серверы из Official MCP Registry.

1. Clone https://github.com/modelcontextprotocol/registry
2. `make publisher`
3. `./bin/mcp-publisher --help`
4. Аутентификация: GitHub OAuth → namespace `io.github.bintocher`
5. Подготовить `server.json` по спецификации реестра
6. Опубликовать: `./bin/mcp-publisher publish`

### Путь B — Кнопка "Add Server" на сайте

1. Перейти на https://glama.ai/mcp/servers
2. Нажать "Add Server"
3. Указать GitHub URL: `https://github.com/bintocher/mcp-superset`

### Путь C — Автоматически

После принятия PR в awesome-mcp-servers — Glama подтянет автоматически.

---

## 5. PulseMCP (pulsemcp.com)

**URL подачи:** https://pulsemcp.com/submit

**Действия:**
1. Перейти на https://pulsemcp.com/submit
2. Тип: MCP Server
3. URL: `https://github.com/bintocher/mcp-superset`
4. Submit

**Альтернатива:** Автоматически подтянется из Official MCP Registry (в течение ~недели). Если не появится — email: hello@pulsemcp.com

**Проверка:** https://www.pulsemcp.com/servers?q=superset

---

## 6. LobeHub (lobehub.com/mcp)

**Репозиторий:** https://github.com/lobehub/lobe-chat-plugins

> **Важно:** LobeHub использует формат OpenAPI/function-calling плагинов, не чистый MCP. Требуется `manifest.json`. Оценить совместимость перед подачей.

**Действия:**
1. Fork `lobehub/lobe-chat-plugins`
2. Скопировать `plugin-template.json` → заполнить:
   ```json
   {
     "author": "bintocher",
     "homepage": "https://github.com/bintocher/mcp-superset",
     "identifier": "mcp-superset",
     "meta": {
       "avatar": "📊",
       "tags": ["superset", "data-visualization", "analytics", "mcp"],
       "title": "MCP Superset",
       "description": "Full-featured MCP server for Apache Superset with 135+ tools"
     }
   }
   ```
3. Положить в `src/` директорию как `mcp-superset.json`
4. Создать PR

---

## 7. mcpservers.org

**URL подачи:** https://mcpservers.org/submit

**Два варианта:**
- **Free:** стандартная очередь модерации
- **Premium ($39):** быстрая модерация, badge, dofollow backlink

**Действия:**
1. Перейти на https://mcpservers.org/submit
2. Server Name: `mcp-superset`
3. Description: `Full-featured MCP server for Apache Superset — 135+ tools for dashboards, charts, datasets, SQL, users, roles, RLS, and more`
4. Link: `https://github.com/bintocher/mcp-superset`
5. Category: `database`
6. Submit

**Альтернатива:** Также автоматически подтянется после принятия PR в awesome-mcp-servers.

---

## 8. Official MCP Registry (registry.modelcontextprotocol.io)

**Приоритет ВЫСОКИЙ** — из него автоматически индексируют Glama.ai и PulseMCP.

**Действия:**
1. Clone https://github.com/modelcontextprotocol/registry
2. `make publisher`
3. `./bin/mcp-publisher --help`
4. Аутентификация: GitHub OAuth → namespace `io.github.bintocher`
5. Подготовить `server.json`
6. Опубликовать: `./bin/mcp-publisher publish`

---

## Статус выполнения

- [x] GitHub topics добавлены (9 тегов: mcp, mcp-server, superset, apache-superset, model-context-protocol, claude, llm, ai-tools, fastmcp)
- [x] smithery.yaml создан
- [x] PR в awesome-mcp-servers — https://github.com/punkpeye/awesome-mcp-servers/pull/3039
- [ ] Smithery.ai — зарегистрировать на сайте (нужен GitHub login)
- [ ] mcp.so — submit на https://mcp.so/submit
- [ ] Official MCP Registry — через mcp-publisher CLI (разблокирует Glama + PulseMCP)
- [ ] PulseMCP — submit на https://pulsemcp.com/submit или через Official Registry
- [ ] mcpservers.org — submit на https://mcpservers.org/submit или автоматически через awesome-list
- [ ] LobeHub — оценить совместимость MCP → PR в lobehub/lobe-chat-plugins

## Рекомендуемый порядок действий

1. **Official MCP Registry** → автоматически попадёт на Glama.ai и PulseMCP
2. **Smithery.ai** → smithery.yaml уже готов, просто зарегистрировать
3. **mcp.so** → быстрая web-форма
4. **mcpservers.org** → быстрая web-форма (free)
5. **LobeHub** → только если подтвердится MCP-совместимость
