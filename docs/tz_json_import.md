# ТЗ: JSON-импорт и CRUD для игровых сущностей

## 1. Scope

Реализовать со стороны бэкенда три режима работы с данными:

| Режим | Описание |
|-------|----------|
| 1 — File/Folder upload | Пользователь выбирает файл или папку в UI → фронт отправляет multipart → импорт в БД |
| 2 — UI CRUD | Пользователь редактирует данные через формы → стандартные CRUD-эндпоинты |
| 3 — Path | Пользователь указывает путь на сервере → API читает файл → тот же импорт |

Режимы 1 и 3 идут через один `ImportService`. Режим 2 — обычный CRUD-слой.

---

## 2. Сущности

| Сущность | Модель | Репозиторий | Маршруты |
|----------|--------|-------------|----------|
| World | `World` | есть (SqliteWorldRepository) | нужны CRUD + import |
| Race | `Race` | **нет** | нужны |
| WorldPerk | `WorldPerk` | **нет** | нужны |
| NamedLocation | `NamedLocation` | **нет** | нужны |
| Seed data | нет моделей | raw SQL | нужны |

Faction — пропускаем (ТЗ помечен "sketch", контракт не готов).

---

## 3. Новые файлы

```
backend/app/
├── db/
│   └── repositories/
│       ├── iRaceRepository.py
│       ├── iWorldPerkRepository.py
│       ├── iNamedLocationRepository.py
│       └── sqlite/
│           ├── raceRepository.py
│           ├── worldPerkRepository.py
│           └── namedLocationRepository.py
├── application/
│   └── import/
│       ├── jsonResolver.py        # режимы 1 и 3
│       ├── importService.py       # единая логика upsert
│       ├── seedService.py         # bulk seed для lookup-таблиц
│       └── importResult.py        # тип ответа
└── api/
    └── routes/
        ├── worlds.py
        ├── races.py
        ├── perks.py
        ├── locations.py
        └── seed.py
```

---

## 4. BaseRepository — расширение

Добавить метод `upsert` в `base.py`:

```python
async def upsert(self, obj: T) -> None:
    cols, vals = to_row(obj)
    placeholders = ", ".join("?" * len(cols))
    sql = f"INSERT OR REPLACE INTO {self._table} ({', '.join(cols)}) VALUES ({placeholders})"
    await self._db.conn.execute(sql, vals)
    await self._db.conn.commit()
```

Используется импортом и CRUD (создание/обновление через единый метод).

---

## 5. JsonResolver

Файл: `app/application/import/jsonResolver.py`

Принимает **один из двух** источников, возвращает распарсенный JSON:

```python
class JsonResolver:
    @staticmethod
    async def from_upload(file: UploadFile) -> dict | list: ...

    @staticmethod
    def from_path(path: str) -> dict | list: ...

    @staticmethod
    async def resolve(
        file: UploadFile | None,
        path: str | None,
    ) -> dict | list: ...
    # Если оба переданы — ошибка 400.
    # Если ни один — ошибка 400.
```

Валидация: файл должен быть валидным UTF-8 JSON, иначе 422.

---

## 6. ImportResult

Файл: `app/application/import/importResult.py`

```python
@dataclass
class ImportError:
    index: int
    message: str

@dataclass
class ImportResult:
    total:     int
    succeeded: int
    failed:    int
    errors:    list[ImportError]
```

HTTP-статус:
- `200` — все записи успешно загружены
- `207` — часть успешно, часть с ошибками
- `422` — невалидный формат файла целиком (JSON не распарсился)

---

## 7. ImportService

Файл: `app/application/import/importService.py`

```python
class ImportService:
    def __init__(
        self,
        world_repo,
        race_repo,
        perk_repo,
        location_repo,
    ): ...

    async def import_world(self, data: dict) -> ImportResult: ...
    async def import_races(self, world_id: str, data: list[dict]) -> ImportResult: ...
    async def import_perks(self, world_id: str, data: list[dict]) -> ImportResult: ...
    async def import_locations(self, world_id: str, data: list[dict]) -> ImportResult: ...

    async def _upsert_many(self, repo, cls, rows: list[dict], inject: dict = {}) -> ImportResult:
        # inject — поля которые добавляются к каждой строке (например world_id)
        # Итерирует rows, конструирует cls(**row | inject), вызывает repo.upsert()
        # Ловит исключения per-row → пишет в errors, продолжает
```

---

## 8. SeedService

Файл: `app/application/import/seedService.py`

Seed-данные — lookup-таблицы без моделей. Используется сырой SQL.

```python
ALLOWED_SEED_TABLES = frozenset({
    "social_status", "age_type",
    "hair_type", "hair_shape", "skin_type",
    "brows_type", "brows_shape", "beard_type", "beard_shape",
    "eye_type", "eye_placement", "eye_iris_type", "eye_lid_type",
    "eye_pupil_type", "eye_roundness",
    "mouth_type", "lip_shape", "teeth_type", "jaw_shape",
    "nose_type", "nose_shape", "ear_type", "ear_shape",
    "breast_type", "breast_shape", "genitals_type",
    "voice_pitch", "voice_timbre", "body_hair_density",
})

class SeedService:
    def __init__(self, db: Database): ...

    async def load(self, data: dict[str, list[dict]]) -> dict[str, ImportResult]:
        # Для каждой таблицы в data:
        #   - проверить что имя в ALLOWED_SEED_TABLES (иначе пропустить с ошибкой)
        #   - INSERT OR REPLACE INTO <table> (...) VALUES (...)
        #   - вернуть результат per-table
```

Формат входного JSON:
```json
{
  "social_status": [
    {"system_social_status": "noble", "display_social_status": "Дворянин", "social_status_weight": 10}
  ],
  "hair_type": [
    {"system_hair_type": "straight", "display_hair_type": "Прямые"}
  ]
}
```

---

## 9. Репозитории

### IRaceRepository

```python
class IRaceRepository(ABC):
    async def get_by_id(self, race_uid: str) -> Race | None: ...
    async def get_by_world(self, world_id: str) -> list[Race]: ...
    async def create(self, race: Race) -> None: ...
    async def update(self, race: Race) -> None: ...
    async def upsert(self, race: Race) -> None: ...
    async def delete(self, race_uid: str) -> None: ...
```

### IWorldPerkRepository

```python
class IWorldPerkRepository(ABC):
    async def get_by_id(self, perk_uid: str) -> WorldPerk | None: ...
    async def get_by_world(self, world_id: str) -> list[WorldPerk]: ...
    async def create(self, perk: WorldPerk) -> None: ...
    async def update(self, perk: WorldPerk) -> None: ...
    async def upsert(self, perk: WorldPerk) -> None: ...
    async def delete(self, perk_uid: str) -> None: ...
```

### INamedLocationRepository

```python
class INamedLocationRepository(ABC):
    async def get_by_id(self, location_uid: str) -> NamedLocation | None: ...
    async def get_by_world(self, world_id: str) -> list[NamedLocation]: ...
    async def get_children(self, parent_uid: str) -> list[NamedLocation]: ...
    async def create(self, loc: NamedLocation) -> None: ...
    async def update(self, loc: NamedLocation) -> None: ...
    async def upsert(self, loc: NamedLocation) -> None: ...
    async def delete(self, location_uid: str) -> None: ...
```

Sqlite-реализации — тонкие обёртки над BaseRepository (аналогично SqliteWorldRepository).

---

## 10. Эндпоинты

### Worlds — `POST /api/worlds`

| Метод | URL | Режим | Описание |
|-------|-----|-------|----------|
| GET | `/worlds` | 2 | Список всех миров |
| GET | `/worlds/{world_id}` | 2 | Получить мир |
| POST | `/worlds` | 2 | Создать мир (JSON body = поля World) |
| PUT | `/worlds/{world_id}` | 2 | Обновить мир |
| DELETE | `/worlds/{world_id}` | 2 | Удалить мир |
| POST | `/worlds/import` | 1, 3 | Импорт мира из файла |

Import body (режим 3):
```json
{"path": "/saves/world.json"}
```
Import body (режим 1): `multipart/form-data`, поле `file`.

### Races — `POST /api/worlds/{world_id}/races`

| Метод | URL | Режим | Описание |
|-------|-----|-------|----------|
| GET | `/worlds/{world_id}/races` | 2 | Список рас мира |
| GET | `/worlds/{world_id}/races/{race_uid}` | 2 | Получить расу |
| POST | `/worlds/{world_id}/races` | 2 | Создать расу |
| PUT | `/worlds/{world_id}/races/{race_uid}` | 2 | Обновить расу |
| DELETE | `/worlds/{world_id}/races/{race_uid}` | 2 | Удалить расу |
| POST | `/worlds/{world_id}/races/import` | 1, 3 | Импорт списка рас |

### Perks — аналогично races

| Метод | URL |
|-------|-----|
| GET | `/worlds/{world_id}/perks` |
| GET | `/worlds/{world_id}/perks/{perk_uid}` |
| POST | `/worlds/{world_id}/perks` |
| PUT | `/worlds/{world_id}/perks/{perk_uid}` |
| DELETE | `/worlds/{world_id}/perks/{perk_uid}` |
| POST | `/worlds/{world_id}/perks/import` |

### Locations — аналогично races

| Метод | URL |
|-------|-----|
| GET | `/worlds/{world_id}/locations` |
| GET | `/worlds/{world_id}/locations/{location_uid}` |
| POST | `/worlds/{world_id}/locations` |
| PUT | `/worlds/{world_id}/locations/{location_uid}` |
| DELETE | `/worlds/{world_id}/locations/{location_uid}` |
| POST | `/worlds/{world_id}/locations/import` |

### Seed — `POST /api/seed`

| Метод | URL | Режим | Описание |
|-------|-----|-------|----------|
| POST | `/seed/import` | 1, 3 | Загрузить seed-данные из файла |
| GET | `/seed/{table}` | 2 | Получить все записи из lookup-таблицы |
| POST | `/seed/{table}` | 2 | Добавить/обновить одну запись |
| DELETE | `/seed/{table}/{pk}` | 2 | Удалить запись |

---

## 11. Форматы JSON-файлов для импорта

### world.json (один объект)
```json
{
  "id": "my_world",
  "name": "Название мира",
  "narrative_language": "ru",
  "stat_schema": {},
  "skill_schema": {},
  "hp_enabled": true,
  "combat_settings": {}
}
```
Необязательные поля можно опускать — применятся дефолты из `World`.

### races.json (массив)
```json
[
  {
    "race_uid": "uid-...",
    "display_race": "Человек",
    "race_traits": {},
    "male": {},
    "female": {}
  }
]
```
`world_id` инжектируется из URL (`/worlds/{world_id}/races/import`), в файле не нужен.

### perks.json / locations.json — аналогично races.json.

---

## 12. Container — изменения

Добавить в `Container`:

```python
# Репозитории
_race_repository:          IRaceRepository | None = None
_perk_repository:          IWorldPerkRepository | None = None
_location_repository:      INamedLocationRepository | None = None

# Сервисы
_import_service:           ImportService | None = None
_seed_service:             SeedService | None = None

def race_repository(self) -> IRaceRepository: ...
def perk_repository(self) -> IWorldPerkRepository: ...
def location_repository(self) -> INamedLocationRepository: ...
def import_service(self) -> ImportService: ...
def seed_service(self) -> SeedService: ...
```

---

## 13. Порядок реализации

1. `BaseRepository.upsert()` + `BaseRepository.delete()`
2. Интерфейсы: IRaceRepository, IWorldPerkRepository, INamedLocationRepository
3. Sqlite-реализации репозиториев
4. `importResult.py`, `jsonResolver.py`
5. `importService.py`, `seedService.py`
6. Container — регистрация новых репо + сервисов
7. Роуты: worlds.py, races.py, perks.py, locations.py, seed.py
8. Регистрация роутеров в главном app
