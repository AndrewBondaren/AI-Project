"""Single SQL writer for Transition + both sides. Uses existing bulk/transaction infra."""

from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import fields
from typing import Any

from app.application.worldData.transitions.transitionValidation import validate_transitions
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionSide import TransitionSideId
from app.db.bulkSql import executemany_rows, iter_batches
from app.db.database import Database, _in_transaction
from app.db.mapper import from_row, to_row
from app.db.models.transition import TransitionRow
from app.db.models.transitionSide import TransitionSideRow
from app.db.models.transitionProjection import from_transition_rows, to_transition_rows
from app.db.repositories.iTransitionRepository import ITransitionRepository, TransitionRepositoryContext


def _insert_sql(row: object, conflict: tuple[str, ...] | None = None) -> str:
    columns, _ = to_row(row)
    sql = (f"INSERT INTO {row.__table__} ({', '.join(columns)}) "
           f"VALUES ({', '.join('?' for _ in columns)})")
    if conflict is not None:
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column not in conflict)
        sql += f" ON CONFLICT ({', '.join(conflict)}) DO UPDATE SET {assignments}"
    return sql


class SqliteTransitionRepository(ITransitionRepository):
    """Instance binds an explicit caller context for one world; no hidden registry reads."""

    def __init__(self, db: Database, context: TransitionRepositoryContext) -> None:
        self._db = db
        self._context = context

    @asynccontextmanager
    async def _aggregate_savepoint(self):
        await self._db.conn.execute("SAVEPOINT transition_aggregate")
        try:
            yield
        except BaseException:
            await self._db.conn.execute("ROLLBACK TO transition_aggregate")
            await self._db.conn.execute("RELEASE transition_aggregate")
            raise
        else:
            await self._db.conn.execute("RELEASE transition_aggregate")

    @asynccontextmanager
    async def _write(self):
        if _in_transaction.get():
            async with self._aggregate_savepoint():
                yield
        else:
            async with self._db.transaction():
                async with self._aggregate_savepoint():
                    yield

    def _validate(self, transitions: Sequence[Transition]) -> list[Transition]:
        context = self._context
        validated = [Transition.model_validate(
            transition.model_dump(mode="json"),
            context={"transition_type_registry": context.registry},
        ) for transition in transitions]
        validate_transitions(context.world_uid, validated, registry=context.registry,
                             levels=context.levels, locations=context.locations, nodes=context.nodes)
        return validated

    async def _read(self, predicate: str, params: Sequence[object]) -> list[Transition]:
        # One SELECT snapshot contains the transition and both sides; no torn reads.
        side_fields = [field.name for field in fields(TransitionSideRow)]
        projection = ", ".join(f"s.{name} AS side_{name}" for name in side_fields)
        sql = (f"SELECT t.*, {projection} FROM transitions t "
               "LEFT JOIN transition_sides s ON s.transition_uid=t.transition_uid "
               f"WHERE t.world_uid=? AND ({predicate}) ORDER BY t.transition_uid, s.side")
        async with self._db.conn.execute(sql, [self._context.world_uid, *params]) as cursor:
            rows = await cursor.fetchall()
        aggregates: dict[str, tuple[TransitionRow, list[TransitionSideRow]]] = {}
        for raw in rows:
            uid = raw[TransitionRow.__pk__]
            if uid not in aggregates:
                aggregates[uid] = (from_row(TransitionRow, raw), [])
            side_wire = {name: raw[f"side_{name}"] for name in side_fields}
            if side_wire[TransitionSideRow.__pk__] is not None:
                aggregates[uid][1].append(from_row(TransitionSideRow, side_wire))
        return [from_transition_rows(row, sides, registry=self._context.registry)
                for row, sides in aggregates.values()]

    async def get(self, uid: str) -> Transition | None:
        rows = await self._read("t.transition_uid=?", [uid])
        return rows[0] if rows else None

    async def create(self, transition: Transition) -> Transition:
        async with self._write():
            validated = self._validate([transition])[0]
            rows = to_transition_rows(validated)
            _, values = to_row(rows.transition)
            await self._db.conn.execute(_insert_sql(rows.transition), values)
            for side in rows.sides:
                _, values = to_row(side)
                await self._db.conn.execute(_insert_sql(side), values)
        return validated

    async def update(self, uid: str, patch: Mapping[str, Any]) -> Transition:
        async with self._write():
            current = await self.get(uid)
            if current is None:
                raise KeyError(uid)
            wire = current.model_dump(mode="json")
            for identity in (TransitionRow.__pk__, "world_uid"):
                if identity in patch and patch[identity] != wire[identity]:
                    raise ValueError(f"update cannot change {identity}")
            nested_fields = {side.value for side in TransitionSideId} | {
                f"{side}_side" for side in TransitionSideId
            }
            for name, value in patch.items():
                if name in nested_fields and isinstance(value, Mapping):
                    wire[name] = {**wire[name], **value}
                else:
                    wire[name] = value
            proposed = Transition.model_validate(wire, context={"transition_type_registry": self._context.registry})
            validated = self._validate([proposed])[0]
            rows = to_transition_rows(validated)
            columns, values = to_row(rows.transition)
            assignments = ", ".join(f"{column}=?" for column in columns if column != TransitionRow.__pk__)
            update_values = [value for column, value in zip(columns, values) if column != TransitionRow.__pk__]
            await self._db.conn.execute(
                f"UPDATE transitions SET {assignments} WHERE transition_uid=? AND world_uid=?",
                [*update_values, uid, self._context.world_uid],
            )
            for side in rows.sides:
                _, values = to_row(side)
                await self._db.conn.execute(_insert_sql(side, (TransitionSideRow.__pk__, "side")), values)
        return validated

    async def delete(self, uid: str) -> bool:
        async with self._write():
            cursor = await self._db.conn.execute(
                "DELETE FROM transitions WHERE transition_uid=? AND world_uid=?",
                [uid, self._context.world_uid],
            )
            return cursor.rowcount > 0

    async def upsert_bulk(self, transitions: Sequence[Transition]) -> int:
        if not transitions:
            return 0
        async with self._write():
            validated = self._validate(transitions)
            uids = list(dict.fromkeys(transition.transition_uid for transition in validated))
            for batch in iter_batches(uids):
                placeholders = ", ".join("?" for _ in batch)
                async with self._db.conn.execute(
                    f"SELECT transition_uid FROM transitions WHERE world_uid<>? "
                    f"AND transition_uid IN ({placeholders})",
                    [self._context.world_uid, *batch],
                ) as cursor:
                    if await cursor.fetchone() is not None:
                        raise ValueError("bulk upsert cannot reassign a transition from another world")
            aggregates = [to_transition_rows(transition) for transition in validated]
            rows = [aggregate.transition for aggregate in aggregates]
            sides = [side for aggregate in aggregates for side in aggregate.sides]
            await executemany_rows(self._db.conn, _insert_sql(rows[0], (TransitionRow.__pk__,)), rows)
            await executemany_rows(self._db.conn, _insert_sql(sides[0], (TransitionSideRow.__pk__, "side")), sides)
        return len(validated)

    def _check_world(self, world_uid: str) -> None:
        if world_uid != self._context.world_uid:
            raise ValueError("query world differs from caller repository context")

    async def owned_by_destination(self, world_uid: str, location_uid: str) -> list[Transition]:
        self._check_world(world_uid)
        return await self._read(
            "EXISTS (SELECT 1 FROM transition_sides owned WHERE owned.transition_uid=t.transition_uid "
            "AND owned.side=? AND owned.owner_location_uid=?)",
            [TransitionSideId.DESTINATION.value, location_uid],
        )

    async def touching_level(self, world_uid: str, level_uid: str) -> list[Transition]:
        self._check_world(world_uid)
        return await self._read(" OR ".join(f"t.{side}_level_uid=?" for side in TransitionSideId),
                                [level_uid] * len(TransitionSideId))

    async def touching_node(self, world_uid: str, node_uid: str) -> list[Transition]:
        self._check_world(world_uid)
        return await self._read(" OR ".join(f"t.{side}_node_uid=?" for side in TransitionSideId),
                                [node_uid] * len(TransitionSideId))
