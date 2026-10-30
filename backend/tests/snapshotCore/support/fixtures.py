"""Temporary SQLite fixtures only; no production adapter or Container binding."""

import sqlite3
import asyncio
import selectors
import tempfile
import time
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.database import Database
from app.db.models.snapshotCore.publicationRows import WorldPublicationRow, PlayerPublicationRow
from app.db.models.snapshotCore.operationRows import PublicationOperationRow, PublicationRequestRow, PublicationOperationEventRow, PublicationOutcomeRow
from app.db.models.snapshotCore.historyRows import WorldSnapshotRow, PlayerSnapshotRow
from app.db.models.artifacts.catalogRows import ArtifactCatalogRow, ArtifactStorageEventRow
from app.db.models.artifacts.holderRows import ArtifactHolderEventRow
from app.db.models.artifacts.leaseRows import ArtifactLeaseEventRow, ArtifactWriterClaimRow

CORE_MODELS = (WorldPublicationRow, PlayerPublicationRow, PublicationOperationRow, PublicationRequestRow, PublicationOperationEventRow, PublicationOutcomeRow, WorldSnapshotRow, PlayerSnapshotRow, ArtifactCatalogRow, ArtifactStorageEventRow, ArtifactHolderEventRow, ArtifactLeaseEventRow, ArtifactWriterClaimRow)
STAMP = "2026-10-30T00:00:00.000000Z"


def insert(conn, table, **values):
    names = tuple(values)
    conn.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
                 tuple(values[name] for name in names))
    return values


def new_database():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA recursive_triggers=OFF")
    schema = Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql"
    conn.executescript(schema.read_text(encoding="utf-8"))
    for world, timeline in (("w1", "t1"), ("w2", "t2")):
        insert(conn, "worlds", world_uid=world, name=world, created_at=STAMP)
        insert(conn, "timelines", timeline_id=timeline, world_uid=world, created_at=STAMP)
    for player, world in (("p1", "w1"), ("p2", "w2"), ("p3", "w1")):
        insert(conn, "character_sheet", character_uid=player, character_type="player",
               display_name=player, world_uid=world, created_at=STAMP)
    insert(conn, "game_sessions", id="s1", world_uid="w1", player_character_id="p1",
           created_at=STAMP, last_active_at=STAMP)
    insert(conn, "game_sessions", id="s2", world_uid="w2", player_character_id="p2",
           created_at=STAMP, last_active_at=STAMP)
    return conn


def validate_models(conn):
    # Exercise the existing Database.validate_schema against real SQLite PRAGMA
    # results. Only its async transport is mocked: no Windows socketpair/worker IO.
    db = Database(":memory:")
    def execute(sql):
        cursor = MagicMock()
        cursor.fetchall = AsyncMock(return_value=conn.execute(sql).fetchall())
        scope = MagicMock()
        scope.__aenter__ = AsyncMock(return_value=cursor)
        scope.__aexit__ = AsyncMock(return_value=False)
        return scope
    db._conn = MagicMock()
    db._conn.execute.side_effect = execute
    pending = db.validate_schema(list(CORE_MODELS))
    try:
        pending.send(None)
    except StopIteration:
        return
    finally:
        pending.close()
    raise AssertionError("schema validation unexpectedly suspended")


def operation(conn, operation_id, kind="snapshot_apply", phase="applying", bound=True, world="w1"):
    insert(conn, "publication_operations", operation_id=operation_id, world_uid=world, kind=kind,
           preparation_fingerprint="a" * 64)
    if bound:
        insert(conn, "publication_requests", operation_id=operation_id, publication_fingerprint="b" * 64)
    return insert(conn, "publication_operation_events", event_id=operation_id + "-event",
                  operation_id=operation_id, predecessor_id=None, event_seq=1, phase=phase, fence=1)


def outcome(conn, operation_id, kind, category=None):
    insert(conn, "publication_outcomes", operation_id=operation_id, outcome_kind=kind, category=category,
           format_version=1, outcome_data=b"opaque schema fixture", outcome_checksum="c" * 64)
    insert(conn, "publication_operation_events", event_id=operation_id + "-terminal",
           operation_id=operation_id, predecessor_id=operation_id + "-event", event_seq=2,
           phase="terminal", fence=1)


def bootstrap(conn):
    return insert(conn, "world_publications", publication_id="root", world_uid="w1", predecessor_id=None,
                  publication_seq=1, operation_id=None, pack_hash=None, snapshot_head_id=None,
                  active_timeline_id=None, gameplay_started=0)


def started(conn):
    bootstrap(conn)
    operation(conn, "activate", kind="pack_activation")
    insert(conn, "world_publications", publication_id="active", world_uid="w1", predecessor_id="root",
           publication_seq=2, operation_id="activate", pack_hash="d" * 64, snapshot_head_id=None,
           active_timeline_id=None, gameplay_started=0)
    outcome(conn, "activate", "pack_activation")
    operation(conn, "start", kind="gameplay_start")
    result = insert(conn, "world_publications", publication_id="started", world_uid="w1", predecessor_id="active",
           publication_seq=3, operation_id="start", pack_hash="d" * 64, snapshot_head_id=None,
           active_timeline_id="t1", gameplay_started=1)
    outcome(conn, "start", "gameplay_start")
    return result


def snapshot_values(conn, operation_id):
    parent = conn.execute("SELECT * FROM world_publications WHERE world_uid='w1' ORDER BY publication_seq DESC LIMIT 1").fetchone()
    turn = 1
    if parent["snapshot_head_id"]:
        turn = conn.execute("SELECT turn_id FROM world_snapshots WHERE snapshot_id=?", (parent["snapshot_head_id"],)).fetchone()[0] + 1
    return dict(snapshot_id=operation_id + "-snapshot", timeline_id="t1", world_uid="w1", turn_id=turn,
                created_at=STAMP, parent_snapshot_id=parent["snapshot_head_id"], snapshot_data=b"metadata",
                snapshot_checksum="e" * 64, operation_id=operation_id, envelope_format_version=1,
                base_pack_hash="d" * 64)


def tick(conn, operation_id="tick", players=()):
    operation(conn, operation_id)
    world = snapshot_values(conn, operation_id)
    insert(conn, "world_snapshots", **world)
    for player in players:
        parent = conn.execute("SELECT * FROM player_publications WHERE player_uid=? ORDER BY publication_seq DESC LIMIT 1", (player,)).fetchone()
        sid = operation_id + "-" + player
        insert(conn, "player_snapshots", player_snapshot_id=sid, player_uid=player, world_uid="w1", timeline_id="t1",
               session_id=None, turn_id=world["turn_id"], created_at=STAMP,
               parent_player_snapshot_id=parent["player_snapshot_id"] if parent else None, operation_id=operation_id,
               envelope_format_version=1, snapshot_data=b"player metadata", snapshot_checksum="e" * 64)
        insert(conn, "player_publications", publication_id=sid + "-pub", player_uid=player,
               predecessor_id=parent["publication_id"] if parent else None,
               publication_seq=parent["publication_seq"] + 1 if parent else 1,
               player_snapshot_id=sid, operation_id=operation_id)
    parent = conn.execute("SELECT * FROM world_publications WHERE world_uid='w1' ORDER BY publication_seq DESC LIMIT 1").fetchone()
    insert(conn, "world_publications", **{**dict(parent), "publication_id": operation_id + "-pub",
           "predecessor_id": parent["publication_id"], "publication_seq": parent["publication_seq"] + 1,
           "operation_id": operation_id, "snapshot_head_id": world["snapshot_id"]})
    outcome(conn, operation_id, "snapshot_apply", "committed")
    return world


def stage(conn, artifact="artifact", op="stage"):
    operation(conn, op, phase="preparing", bound=False)
    insert(conn, "artifact_lease_events", event_id=op + "-lease", operation_id=op,
           predecessor_id=None, event_seq=1, fence=1, admission_open=1)
    descriptor = insert(conn, "artifact_catalog", artifact_id=artifact, kind="blob", format_key="test.blob",
                        format_version=1, content_hash=sha256(artifact.encode()).hexdigest(), nbytes=1, row_count=None)
    hold = insert(conn, "artifact_holder_events", event_id=op + "-hold", artifact_id=artifact,
                  holder_kind="operation", operation_id=op, fence=1, retained_artifact_id=None,
                  world_snapshot_id=None, player_snapshot_id=None, predecessor_id=None, event_seq=1, event_kind="acquire")
    claim = insert(conn, "artifact_writer_claims", event_id=op + "-writer", artifact_id=artifact,
                   operation_id=op, fence=1, predecessor_id=None, event_seq=1, event_kind="acquire")
    storage = insert(conn, "artifact_storage_events", event_id=op + "-sealed", artifact_id=artifact,
                     predecessor_id=None, event_seq=1, kind="sealed")
    return descriptor, hold, claim, storage


def close_writers(conn, op="stage"):
    insert(conn, "artifact_writer_claims", event_id=op + "-writer-release", artifact_id="artifact",
           operation_id=op, fence=1, predecessor_id=op + "-writer", event_seq=2, event_kind="release")
    insert(conn, "artifact_lease_events", event_id=op + "-closed", operation_id=op,
           predecessor_id=op + "-lease", event_seq=2, fence=1, admission_open=0)


def run_async(coroutine):
    # Real tasks, worker threads and SQLite; only the unused network wakeup
    # socket is replaced by bounded selector polling in this restricted host.
    def no_pipe(loop):
        loop._ssock = loop._csock = None
    def factory():
        selector = selectors.SelectSelector()
        selector.select = lambda timeout=None: (time.sleep(min(0.002, timeout) if timeout is not None else 0.002), [])[1]
        return asyncio.SelectorEventLoop(selector)
    with patch.object(asyncio.SelectorEventLoop, "_make_self_pipe", no_pipe), patch.object(
            asyncio.SelectorEventLoop, "_close_self_pipe", lambda loop: None):
        with asyncio.Runner(loop_factory=factory) as runner:
            return runner.run(coroutine)


@asynccontextmanager
async def live_database(path=None, seed=True):
    from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
    from app.db.repositories.sqlite.snapshotCore.publications.worldPublicationStore import SqliteWorldPublicationStore
    from app.db.repositories.sqlite.snapshotCore.publications.playerPublicationStore import SqlitePlayerPublicationStore
    from app.db.repositories.sqlite.snapshotCore.history.snapshotHistoryStore import SqliteSnapshotHistoryStore
    from app.db.repositories.sqlite.snapshotCore.operations.operationStore import SqliteOperationStore
    workspace = Path(__file__).resolve().parents[4]
    root = (workspace / "backend/.tmp_snapshot_core").resolve()
    assert root.is_relative_to(workspace)
    root.mkdir(exist_ok=True)
    temporary = tempfile.TemporaryDirectory(dir=root) if path is None else None
    filename = str(Path(temporary.name) / "test.db") if temporary is not None else path
    db = Database(filename)
    try:
        await db.connect()
        # Schema setup only; runtime publication tests restore FULL durability.
        await db.conn.execute("PRAGMA synchronous=OFF")
        await db.apply_migrations()
        await db.conn.execute("PRAGMA synchronous=FULL")
        if seed:
            async with db.transaction():
                await db.conn.execute("INSERT INTO worlds(world_uid,name,created_at) VALUES ('w1','w1',?)", (STAMP,))
                await db.conn.execute("INSERT INTO timelines(timeline_id,world_uid,created_at) VALUES ('t1','w1',?)", (STAMP,))
                await db.conn.execute("INSERT INTO character_sheet(character_uid,character_type,display_name,world_uid,created_at) VALUES ('p1','player','p1','w1',?)", (STAMP,))
        commits = SqlitePublicationCommitStore(db)
        world = SqliteWorldPublicationStore(commits)
        players = SqlitePlayerPublicationStore(commits)
        history = SqliteSnapshotHistoryStore(commits)
        operations = SqliteOperationStore(commits, world, players)
        yield db, commits, world, players, history, operations
    finally:
        await db.disconnect()
        if temporary is not None:
            temporary.cleanup()


async def live_started(bundle):
    from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind, ArtifactFormatRegistry
    from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
    from app.dataModel.registryKey import RegistryKey
    from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
    from app.dataModel.worldSnapshot.results.publication import PackActivationResult, PackActivationDisposition, GameplayStarted
    db, commits, world, players, history, operations = bundle
    async with commits.transaction("bootstrap") as scope:
        root = await world.initialize(scope, "w1")
    await operations.claim_publication(OperationKind.PACK_ACTIVATION, "activate", "w1", "a" * 64, "b" * 64)
    active = WorldPublicationRef(world_uid="w1", publication_id="active", pack_hash="d" * 64,
        snapshot_head=None, active_timeline_id=None, gameplay_started=False)
    artifact = ArtifactRef(kind=ArtifactKind.BLOB, format_key=RegistryKey[ArtifactFormatRegistry]("test.manifest"),
                           format_version=1, content_hash="d" * 64, nbytes=0)
    async with commits.transaction("activate") as scope:
        await world.compare_append(scope, root, active)
        await operations.record_terminal(scope, PackActivationResult(operation_id="activate", request_fingerprint="b" * 64,
            manifest=artifact, disposition=PackActivationDisposition.ACTIVE, publication=active))
    await operations.claim_publication(OperationKind.GAMEPLAY_START, "start", "w1", "a" * 64, "b" * 64)
    started_ref = WorldPublicationRef(world_uid="w1", publication_id="started", pack_hash="d" * 64,
        snapshot_head=None, active_timeline_id="t1", gameplay_started=True)
    async with commits.transaction("start") as scope:
        await world.compare_append(scope, active, started_ref)
        await operations.record_terminal(scope, GameplayStarted(operation_id="start", request_fingerprint="b" * 64,
                                                               publication=started_ref))
    return started_ref


async def live_tick(bundle, operation_id="tick", *, fail=False, entered=None, hold=None):
    from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
    from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef, PlayerSnapshotRef
    from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef, PlayerHeadExpectation
    from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata, PlayerSnapshotMetadata
    from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult, SnapshotCommitRefs
    from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
    db, commits, world, players, history, operations = bundle
    expected = await world.read("w1")
    claim = await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, operation_id, "w1", "a" * 64, "b" * 64)
    world_ref = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id=operation_id + "-world")
    player_ref = PlayerSnapshotRef(player_uid="p1", snapshot_id=operation_id + "-player")
    old_player = await players.read("p1")
    turn = 1 if expected.snapshot_head is None else (await history.read(expected.snapshot_head)).turn_id + 1
    metadata = WorldSnapshotMetadata(ref=world_ref, parent=expected.snapshot_head, operation_id=operation_id, turn_id=turn,
        created_at=STAMP, envelope_format_version=1, base_pack_hash="d" * 64, state_refs=(), history_refs=(), retained_artifacts=())
    player = PlayerSnapshotMetadata(ref=player_ref, parent=old_player, operation_id=operation_id, turn_id=turn,
        created_at=STAMP, envelope_format_version=1, state_refs=(), history_refs=(), retained_artifacts=())
    publication = WorldPublicationRef(world_uid="w1", publication_id=operation_id + "-pub", pack_hash="d" * 64,
        snapshot_head=world_ref, active_timeline_id="t1", gameplay_started=True)
    result = SnapshotApplyResult(category=SnapshotApplyOutcomeKind.COMMITTED, operation_id=operation_id,
        request_fingerprint="b" * 64, committed=SnapshotCommitRefs(world_snapshot=world_ref,
            player_snapshots=(player_ref,), publication=publication), diagnostics=())
    async with commits.transaction(operation_id) as scope:
        await history.append(scope, metadata, ())
        await history.append(scope, player, ())
        await world.compare_append(scope, expected, publication)
        if fail:
            raise RuntimeError("injected failure between world and player publication")
        await players.compare_append(scope, PlayerHeadExpectation(player_uid="p1", expected_head=old_player), player_ref, operation_id)
        await operations.record_terminal(scope, result)
        if entered is not None:
            entered.set()
        if hold is not None:
            await hold.wait()
    return claim, result
