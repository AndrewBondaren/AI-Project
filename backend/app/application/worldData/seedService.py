from fastapi import HTTPException

from app.api.schemas.imports import ImportError, ImportResult
from app.db.database import Database

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

    def __init__(self, db: Database) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Import (режимы 1 и 3)
    # ------------------------------------------------------------------

    async def import_from_json(self, data: dict[str, list[dict]]) -> dict[str, ImportResult]:
        results: dict[str, ImportResult] = {}

        for table, rows in data.items():
            if table not in ALLOWED_SEED_TABLES:
                results[table] = ImportResult(
                    total=len(rows), succeeded=0, failed=len(rows),
                    errors=[ImportError(index=0, message=f"Unknown table: '{table}'")],
                )
                continue
            results[table] = await self._upsert_table(table, rows)

        return results

    async def _upsert_table(self, table: str, rows: list[dict]) -> ImportResult:
        succeeded = 0
        errors: list[ImportError] = []

        for i, row in enumerate(rows):
            try:
                await self._upsert_row(table, row)
                succeeded += 1
            except Exception as e:
                errors.append(ImportError(index=i, message=str(e)))

        await self._db.conn.commit()
        return ImportResult(total=len(rows), succeeded=succeeded, failed=len(errors), errors=errors)

    async def _upsert_row(self, table: str, row: dict) -> None:
        cols = list(row.keys())
        vals = [row[c] for c in cols]
        placeholders = ", ".join("?" * len(cols))
        sql = f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        await self._db.conn.execute(sql, vals)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def export_all(self) -> dict[str, list[dict]]:
        result = {}
        for table in ALLOWED_SEED_TABLES:
            async with self._db.conn.execute(f"SELECT * FROM {table}") as cur:
                rows = await cur.fetchall()
            result[table] = [dict(r) for r in rows]
        return result

    # ------------------------------------------------------------------
    # CRUD (режим 2)
    # ------------------------------------------------------------------

    async def get_all(self, table: str) -> list[dict]:
        self._validate_table(table)
        async with self._db.conn.execute(f"SELECT * FROM {table}") as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def upsert_one(self, table: str, row: dict) -> None:
        self._validate_table(table)
        await self._upsert_row(table, row)
        await self._db.conn.commit()

    async def delete_one(self, table: str, pk_val: str) -> None:
        self._validate_table(table)
        # PK всех seed-таблиц следует паттерну system_{table} — это намеренное соглашение.
        # system_* колонки — стабильные идентификаторы, не зависящие от языка и переименований.
        # Не заменять на словарь: таблица вайтлистирована выше, паттерн гарантирует безопасность.
        pk_col = f"system_{table}"
        await self._db.conn.execute(f"DELETE FROM {table} WHERE {pk_col} = ?", [pk_val])
        await self._db.conn.commit()

    def _validate_table(self, table: str) -> None:
        if table not in ALLOWED_SEED_TABLES:
            raise HTTPException(status_code=400, detail=f"Unknown seed table: '{table}'")
