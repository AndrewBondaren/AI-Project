import sqlite3
import unittest
from unittest.mock import AsyncMock, patch

from app.application.publication.errors import PublicationInfrastructureError
from app.application.time.calendar.projection import CalendarProjector
from app.application.time.composition.factory import make_time_reader
from app.application.time.reads.snapshotSource import SnapshotTimeReadSource
from app.application.worldSnapshot.service.acceptedStateReader import AcceptedStateReader
from app.dataModel.time.reads.capture import HistoricalTimeCapture, TimeCapture
from app.dataModel.time.reads.request import CurrentTimeRead, HistoricalTimeRead
from app.dataModel.time.results.errors import TimePublicationConflict, TimeStateUnavailable, TimeUnavailableReason
from app.dataModel.time.storage.state import CLOCK_SECTION, PublicationTimeState, StoredTimeState, TimeClockState
from app.dataModel.time.values.point import TimePoint
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef
from app.db.models.timeStates import TimePublicationRow, TimeSnapshotRow
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.timeStateReader import SqliteTimeStateReader
from tests.snapshotCore.storage.publication.test_accepted_state_reader import publish
from tests.snapshotCore.storage.publication.test_history import OTHER, receipt
from tests.snapshotCore.support.fixtures import live_database, live_started, run_async


class SnapshotTimeReadTests(unittest.TestCase):
    def test_values_after_commit_and_inherited_section(self):
        async def check():
            async with live_database() as bundle:
                db, commits, *_ = bundle
                initial = await live_started(bundle)
                reader = make_time_reader(commits)
                unavailable = TimeStateUnavailable(world_uid="w1", reason=TimeUnavailableReason.SOURCE_UNRESOLVED)
                self.assertEqual(await reader.read_pinned(initial), unavailable)
                origin = TimePoint(world_uid="w1", timeline_id="t1", seconds=17, nanoseconds=8)
                binding = PublicationTimeState(publication=initial, state=TimeClockState(point=origin))
                async with commits.transaction("fixture") as scope:
                    await ScopedSqliteAccess(commits.registry).insert(scope, TimePublicationRow(
                        initial.publication_id, binding.model_dump_json()))
                first = await reader.read_current(CurrentTimeRead(expected=initial))
                self.assertEqual(first, TimeCapture(publication=initial, point=origin))
                assert isinstance(first, TimeCapture)
                pinned = first.publication
                snapshot = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="s")
                section = SectionStateRef(snapshot=snapshot, section_key=CLOCK_SECTION, format_version=1)
                later = origin.model_copy(update={"seconds": 321, "nanoseconds": 123})
                payload = StoredTimeState(ref=section, state=TimeClockState(point=later))
                async with live_database(db.path, seed=False) as writer:
                    async def insert_payload(scope):
                        await ScopedSqliteAccess(writer[1].registry).insert(scope, TimeSnapshotRow(
                            snapshot.snapshot_id, payload.model_dump_json()))
                    target = await publish(writer, initial, "op", snapshot, section,
                                           (receipt(key=CLOCK_SECTION, states=(section,)),), insert_payload=insert_payload)
                    async with writer[0].transaction():
                        for table in ("time_publication_states", "time_snapshot_states"):
                            for statement in (f"UPDATE {table} SET payload='changed'", f"DELETE FROM {table}",
                                              f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
                                with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                                    await writer[0].conn.execute(statement)
                self.assertEqual(await reader.read_pinned(pinned), TimeCapture(publication=pinned, point=origin))
                current = TimeCapture(publication=target, point=later)
                self.assertEqual(await reader.read_pinned(target), current)
                self.assertEqual(await reader.read_current(CurrentTimeRead(expected=pinned)),
                                 TimePublicationConflict(expected=pinned, observed=target))
                self.assertEqual(await reader.read_current(CurrentTimeRead(expected=target)), current)
                self.assertEqual(await reader.read_historical(HistoricalTimeRead(snapshot=snapshot)),
                                 HistoricalTimeCapture(snapshot=snapshot, point=later))
                child = snapshot.model_copy(update={"snapshot_id": "child"})
                inherited = await publish(bundle, target, "next", child, section, ())
                for table, key, old, new in (
                    ("time_publication_states", "publication_id", pinned.publication_id, target.publication_id),
                    ("time_snapshot_states", "snapshot_id", snapshot.snapshot_id, child.snapshot_id),
                ):
                    with self.subTest(table=table), self.assertRaisesRegex(sqlite3.OperationalError, "rowid"):
                        async with db.transaction():
                            await db.conn.execute(
                                f"INSERT OR REPLACE INTO {table}(rowid,{key},payload) "
                                f"SELECT rowid,?,payload FROM {table} WHERE {key}=?", (new, old))
                self.assertEqual(await reader.read_pinned(pinned), TimeCapture(publication=pinned, point=origin))
                self.assertEqual(await reader.read_historical(HistoricalTimeRead(snapshot=snapshot)),
                                 HistoricalTimeCapture(snapshot=snapshot, point=later))
                self.assertEqual(await reader.read_pinned(inherited), TimeCapture(publication=inherited, point=later))
                self.assertEqual(await reader.read_historical(HistoricalTimeRead(snapshot=child)),
                                 HistoricalTimeCapture(snapshot=child, point=later))
                absent = snapshot.model_copy(update={"snapshot_id": "absent"})
                self.assertEqual(await reader.read_historical(HistoricalTimeRead(snapshot=absent)),
                                 TimeStateUnavailable(world_uid="w1", reason=TimeUnavailableReason.SNAPSHOT_MISSING))
                for field in ("world_uid", "timeline_id"):
                    with self.assertRaises(PublicationInfrastructureError):
                        await reader.read_historical(HistoricalTimeRead(snapshot=snapshot.model_copy(update={field: "other"})))
        with patch.object(CalendarProjector, "project") as project:
            run_async(check())
            project.assert_not_called()

    def test_inherited_head_reads_child_binding_in_same_scope(self):
        async def check():
            async with live_database() as bundle:
                initial = await live_started(bundle)
                head = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="parent")
                branch = initial.model_copy(update={"active_timeline_id": "child", "snapshot_head": head})
                point = TimePoint(world_uid="w1", timeline_id="child", seconds=57, nanoseconds=9)
                binding = PublicationTimeState(publication=branch, state=TimeClockState(point=point))
                commits = bundle[1]
                access = ScopedSqliteAccess(commits.registry)
                async with commits.transaction("fixture") as scope:
                    await access.insert(scope, TimePublicationRow(branch.publication_id, binding.model_dump_json()))
                publications, history = AsyncMock(), AsyncMock()
                publications.read_exact.return_value = branch
                store = AsyncMock(wraps=SqliteTimeStateReader(access))
                reader = make_time_reader(SnapshotTimeReadSource(commits, publications,
                                          AcceptedStateReader(publications, history), store))
                self.assertEqual(await reader.read_pinned(branch), TimeCapture(publication=branch, point=point))
                scope = publications.read_exact.await_args.kwargs["scope"]
                store.read_binding.assert_awaited_once_with(branch, scope)
                store.read_section.assert_not_awaited()
                history.read.assert_not_awaited()
        run_async(check())

    def test_missing_or_unsupported_clock(self):
        async def check(key, version):
            async with live_database() as bundle:
                initial = await live_started(bundle)
                reader = make_time_reader(bundle[1])
                snapshot = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="s")
                section = SectionStateRef(snapshot=snapshot, section_key=key, format_version=version)
                target = await publish(bundle, initial, "op", snapshot, section, (receipt(key=key, states=(section,)),))
                if version == 2:
                    point = TimePoint(world_uid="w1", timeline_id="t1", seconds=42, nanoseconds=1)
                    payload = StoredTimeState(ref=section, state=TimeClockState(point=point))
                    async with bundle[1].transaction("fixture") as scope:
                        await ScopedSqliteAccess(bundle[1].registry).insert(scope, TimeSnapshotRow(
                            snapshot.snapshot_id, payload.model_dump_json()))
                missing = TimeStateUnavailable(world_uid="w1", reason=TimeUnavailableReason.SOURCE_UNRESOLVED)
                self.assertEqual(await reader.read_pinned(target), missing)
                self.assertEqual(await reader.read_historical(HistoricalTimeRead(snapshot=snapshot)), missing)
        for key, version in ((OTHER, 1), (CLOCK_SECTION, 1), (CLOCK_SECTION, 2)):
            with self.subTest(key=key, version=version):
                run_async(check(key, version))

    def test_corrupt_snapshot_apply_head(self):
        async def check(missing_head):
            async with live_database() as bundle:
                db, commits, *_ = bundle
                initial = await live_started(bundle)
                snapshot = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="s")
                section = SectionStateRef(snapshot=snapshot, section_key=CLOCK_SECTION, format_version=1)
                target = await publish(bundle, initial, "op", snapshot, section,
                                       (receipt(key=CLOCK_SECTION, states=(section,)),))
                async with db.transaction():
                    if missing_head:
                        await db.conn.execute("DROP TRIGGER world_publications_no_update")
                        await db.conn.execute("UPDATE world_publications SET snapshot_head_id=NULL WHERE publication_id=?",
                                              (target.publication_id,))
                    else:
                        await db.conn.execute("INSERT INTO timelines(timeline_id,world_uid,created_at) "
                                              "SELECT 'other',world_uid,created_at FROM timelines WHERE timeline_id='t1'")
                        await db.conn.execute("DROP TRIGGER world_snapshots_no_update")
                        await db.conn.execute("UPDATE world_snapshots SET timeline_id='other' WHERE snapshot_id='s'")
                reader = make_time_reader(commits)
                with self.assertRaises(PublicationInfrastructureError):
                    await reader.read_current(CurrentTimeRead(expected=target))
                with self.assertRaises(PublicationInfrastructureError):
                    await reader.read_pinned(target)
        for missing_head in (False, True):
            with self.subTest(missing_head=missing_head):
                run_async(check(missing_head))
