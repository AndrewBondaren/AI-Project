import asyncio
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

import aiosqlite

_in_transaction: ContextVar[bool] = ContextVar("_in_transaction", default=False)

log = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

BULK_CACHE_SIZE = -64000  # 64 MB page cache on bootstrap connection


class Database:

    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._bootstrap_conn: aiosqlite.Connection | None = None
        self._bulk_lock = asyncio.Lock()

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        self._bootstrap_conn = await aiosqlite.connect(self.path)
        self._bootstrap_conn.row_factory = aiosqlite.Row
        await self._bootstrap_conn.execute("PRAGMA journal_mode=WAL")
        await self._bootstrap_conn.execute("PRAGMA foreign_keys=ON")
        await self._bootstrap_conn.execute("PRAGMA synchronous=NORMAL")
        await self._bootstrap_conn.execute("PRAGMA temp_store=MEMORY")
        await self._bootstrap_conn.execute(f"PRAGMA cache_size={BULK_CACHE_SIZE}")

    async def disconnect(self) -> None:
        if self._bootstrap_conn:
            await self._bootstrap_conn.close()
            self._bootstrap_conn = None
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
        async with self.transaction_on(self.main_conn):
            yield self.main_conn

    @asynccontextmanager
    async def transaction_on(self, conn: aiosqlite.Connection):
        """BEGIN/COMMIT/ROLLBACK on the given connection (TR-PAR-6 writer txn)."""
        token = _in_transaction.set(True)
        await conn.execute("BEGIN")
        try:
            yield conn
            await conn.execute("COMMIT")
        except Exception:
            await conn.execute("ROLLBACK")
            raise
        finally:
            _in_transaction.reset(token)

    @asynccontextmanager
    async def bulk_write_lock(self):
        """TR-PAR-5/6: serialize bootstrap bulk writers (lock only, no conn routing).

        See ``docs/tz_terrain_generation.md`` § TR-PAR-6.
        """
        if self._bootstrap_conn is None:
            raise RuntimeError("Database.connect() не был вызван")
        async with self._bulk_lock:
            yield

    @property
    def conn(self) -> aiosqlite.Connection:
        """OLTP connection — always main (TR-PAR-6: no ContextVar routing)."""
        return self.main_conn

    @property
    def main_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect() не был вызван")
        return self._conn

    @property
    def bootstrap_conn(self) -> aiosqlite.Connection:
        """Bootstrap bulk connection — bulk PRAGMA set once in connect()."""
        if self._bootstrap_conn is None:
            raise RuntimeError("Database.connect() не был вызван")
        return self._bootstrap_conn


def _parse_version(filename: str) -> int | None:
    try:
        return int(filename.split("_")[0])
    except (ValueError, IndexError):
        return None
