import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

import aiosqlite

_in_transaction: ContextVar[bool] = ContextVar("_in_transaction", default=False)

log = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:

    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def disconnect(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def apply_migrations(self) -> None:
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        await self._conn.commit()

        async with self._conn.execute(
            "SELECT version FROM schema_migrations"
        ) as cur:
            applied = {row[0] for row in await cur.fetchall()}

        files = sorted(
            f for f in _MIGRATIONS_DIR.glob("*.sql")
            if (version := _parse_version(f.name)) is not None
            and version not in applied
        )

        for f in files:
            version = _parse_version(f.name)
            sql = f.read_text(encoding="utf-8")
            await self._conn.executescript(sql)
            await self._conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) "
                "VALUES (?, datetime('now'))",
                (version,),
            )
            await self._conn.commit()
            log.info("Applied migration %04d (%s)", version, f.name)

        if files:
            log.info("Migrations complete: %d applied", len(files))
        else:
            log.debug("No pending migrations")

    async def validate_schema(self, models: list[type]) -> None:
        from app.db.mapper import model_columns
        errors: list[str] = []
        for cls in models:
            async with self._conn.execute(
                f"PRAGMA table_info({cls.__table__})"
            ) as cur:
                rows = await cur.fetchall()
            db_cols = {row["name"] for row in rows}
            missing = model_columns(cls) - db_cols
            if missing:
                errors.append(
                    f"  {cls.__name__} (table '{cls.__table__}'): "
                    f"missing columns {sorted(missing)}"
                )
        if errors:
            raise RuntimeError("Schema mismatch:\n" + "\n".join(errors))
        log.debug("Schema validation passed for %d models", len(models))

    @asynccontextmanager
    async def transaction(self):
        token = _in_transaction.set(True)
        await self._conn.execute("BEGIN")
        try:
            yield self._conn
            await self._conn.execute("COMMIT")
        except Exception:
            await self._conn.execute("ROLLBACK")
            raise
        finally:
            _in_transaction.reset(token)

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect() не был вызван")
        return self._conn


def _parse_version(filename: str) -> int | None:
    try:
        return int(filename.split("_")[0])
    except (ValueError, IndexError):
        return None
