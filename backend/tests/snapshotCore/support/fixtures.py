"""Temporary SQLite fixtures only; no production adapter or Container binding."""

import sqlite3
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
