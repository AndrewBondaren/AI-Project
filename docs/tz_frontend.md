# ТЗ: Архитектура фронтенда

## 1. Технологии

| Слой | Технология |
|------|-----------|
| UI | React 19 + Vite |
| Нативное окно | Electron |
| Роутинг | react-router-dom |
| Стили | CSS Modules |
| Сборка | один `package.json`, один `node_modules` |

---

## 2. Структура проекта

```
frontend/
├── package.json              ← один npm-проект (Electron + Vite + React)
├── vite.config.js            ← @ алиас для src/, VITE_API_URL
├── .env                      ← VITE_API_URL=http://127.0.0.1:8000/api
├── index.html
├── electron/
│   ├── main.js               ← BrowserWindow + IPC dialog:openFile
│   └── preload.js            ← contextBridge: window.electron.openFile()
└── src/
    ├── config.js             ← читает import.meta.env.VITE_API_URL
    ├── main.jsx
    ├── App.jsx               ← router setup
    ├── platform/
    │   └── fileSystem.js     ← платформо-зависимый выбор файла
    ├── api/
    │   ├── chatApi.js
    │   ├── sessionApi.js
    │   ├── settingsApi.js
    │   └── worldApi.js
    ├── layouts/
    │   ├── AppLayout.jsx     ← nav + общая обёртка
    │   └── AppLayout.module.css
    ├── features/
    │   ├── session/
    │   │   ├── ui/
    │   │   ├── hooks/
    │   │   └── service.js
    │   ├── chat/
    │   │   ├── ui/
    │   │   ├── hooks/
    │   │   └── service.js
    │   └── settings/
    │       ├── layout/       ← sub-nav вкладки настроек
    │       ├── world/        ← placeholder
    │       │   └── ui/
    │       └── backend/
    │           ├── ui/
    │           ├── hooks/
    │           └── service.js
    └── shared/
        ├── ui/               ← Button, Input, Modal и др. переиспользуемые компоненты
        └── styles/
            ├── variables.css ← цвета, отступы, типографика
            ├── reset.css
            └── global.css
```

---

## 3. Роутинг

| Маршрут | Экран | Фича |
|---------|-------|------|
| `/` | Список сессий + "Новая игра" | session |
| `/new` | Выбор мира | session |
| `/new/:worldId` | Выбор / создание персонажа | session |
| `/chat/:sessionId` | Чат | chat |
| `/settings/backend` | Настройки бэка | settings/backend |
| `/settings/world` | Настройки мира | settings/world (placeholder) |

---

## 4. Слои и ответственность

| Слой | Файл | Ответственность |
|------|------|----------------|
| Transport | `api/*.js` | Сырые HTTP/SSE вызовы, бросает ошибку при !ok |
| Service | `features/*/service.js` | Бизнес-логика, маппинг запросов/ответов, перехват и трансформация ошибок |
| Hooks | `features/*/hooks/*.js` | State, lifecycle, вызывает service |
| UI | `features/*/ui/*.jsx` | Только разметка и пропсы, никакой логики |
| CSS | `features/*/ui/*.module.css` | Стили изолированы по компоненту |

---

## 5. Флоу создания сессии

```
/ → выбрать "Новая игра"
  → /new (список миров с бэка)
  → выбрать мир → /new/:worldId (персонажи этого мира)
  → выбрать персонажа или импортировать из JSON или создать через процесс создания персонажа - TODO
  → POST /api/sessions { world_uid, character_id }
  → redirect /chat/:sessionId
```

Если сессия для этой пары мир+персонаж уже существует — бэк возвращает существующую (идемпотентно).

---

## 5а. Жизненный цикл сессии

- `GameSession` в БД хранится постоянно — не удаляется при закрытии
- При закрытии клиентом: очищается только snapshot (in-memory состояние пайплайна) через `snapshot_store.delete()`
- Данные мира и персонажа остаются привязаны к сессии в БД
- При возврате: если snapshot есть — resume, если нет — начинаем с чистого листа (история из `messages` сохраняется)

---

## 5б. Список сессий — экран `/`

Показывает все существующие сессии пользователя в виде карточек.

**Что отображает карточка:**
- Название мира
- Имя персонажа
- Дата последней активности

**Удалённые сущности:** если мир или персонаж были удалены из БД, карточка явно сообщает об этом:
- `world_name: null` → показать `"Мир удалён"`
- `character_name: null` → показать `"Персонаж удалён"`
- Оба null — показать оба предупреждения

**Почему бэк обогащает данные, а не фронт джойнит сам:**

Клиентский джойн создаёт семантическую неоднозначность: `undefined` при поиске мира в локальном массиве означает одновременно "мир удалён", "запрос упал с ошибкой" или "данные ещё не загружены". Различить невозможно — нельзя корректно отобразить "Мир удалён" вместо пустого поля.

Бэковый LEFT JOIN даёт однозначный контракт: `null` = сущности нет в БД.

**Контракт ответа `GET /api/sessions`:**
```json
[
  {
    "id": "...",
    "world_uid": "...",
    "world_name": "Мир Арден",
    "character_id": "...",
    "character_name": "Арден Стоунхарт",
    "last_active_at": "2026-05-24T10:00:00Z"
  }
]
```

**Реализация на бэке:** SQL SELECT с LEFT JOIN:
```sql
SELECT gs.id, gs.world_uid, gs.player_character_id AS character_id,
       gs.last_active_at,
       w.name AS world_name,
       p.display_name AS character_name
FROM game_sessions gs
LEFT JOIN worlds          w ON w.world_uid    = gs.world_uid
LEFT JOIN character_sheet p ON p.character_uid = gs.player_character_id
```

---

## 6. Работа с файловой системой

Файлы выбираются через нативный диалог Electron:

```
electron/main.js      → ipcMain.handle('dialog:openFile', () => dialog.showOpenDialog(...))
electron/preload.js   → contextBridge: window.electron.openFile()
platform/fileSystem.js → в Electron вызывает window.electron.openFile()
                         в браузере — <input type="file"> (для будущего)
```

Фичи вызывают только `platform/fileSystem.js` — не знают об Electron напрямую.

---

## 7. Мультиплатформенность

Скрипты в `frontend/package.json`:

```json
"dev:browser":    "vite",
"dev:electron":   "concurrently \"vite\" \"wait-on http://localhost:5173 && electron .\"",
"build:web":      "vite build",
"build:electron": "vite build && electron-builder"
```

React-приложение платформо-нейтрально — вся платформо-специфика изолирована в `platform/`.

---

## 8. Обработка ошибок

- `api/` — бросает сырую ошибку (HTTP статус + тело)
- `service.js` — перехватывает, трансформирует в понятное сообщение
- `hooks/` — передаёт в UI state
- UI — отображает, не знает об HTTP

---

## 9. Конфигурация

- `VITE_API_URL` в `.env` — базовый URL бэкенда
- `src/config.js` — единственное место где читается env
- Хардкод URL запрещён

---

## 10. Shared компоненты

Компонент попадает в `shared/ui/` только если используется в двух и более фичах. Создаются по мере необходимости, не заранее.

CSS-переменные (цвета, отступы) — в `shared/styles/variables.css`. Все компоненты используют переменные, не хардкодят значения.
