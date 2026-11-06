import sys
import unittest
from unittest.mock import patch
from tests.snapshotCore.support.fixtures import live_database, live_started, run_async
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.worldSnapshot.contracts.context import SnapshotValidationContext
from app.application.worldSnapshot.service.worldSnapshotService import WorldSnapshotService, SnapshotCasConflict
from app.application.publication.errors import UnknownCommitOutcome
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.results.publication import CasTransactionOutcome

async def probe(mode):
    async with live_database() as bundle, live_database(bundle[0].path, seed=False) as peer:
        db, commits, world, players, history, operations = bundle
        base = await live_started(bundle)
        expected = base.model_copy(update={'publication_id': 'stale'})
        service = WorldSnapshotService(SectionRegistry(), world, players, history)
        original = commits.driver.rollback
        captured = []
        async def rollback(conn):
            error = sys.exception()
            assert isinstance(error, SnapshotCasConflict)
            captured.append(error)
            assert error.trace.transaction_outcome is CasTransactionOutcome.PENDING
            if mode == 'before':
                raise OSError('injected rollback failure')
            result = await original(conn)
            assert error.trace.transaction_outcome is CasTransactionOutcome.PENDING
            if mode == 'after':
                raise OSError('injected lost acknowledgement')
            return result
        with patch.object(commits.driver, 'rollback', side_effect=rollback):
            try:
                async with commits.transaction('candidate') as scope:
                    await db.conn.execute("UPDATE worlds SET name='tentative' WHERE world_uid='w1'")
                    ctx = SnapshotValidationContext('candidate', expected, (), (), scope.read_scope)
                    ref = WorldSnapshotRef(world_uid='w1', timeline_id='t1', snapshot_id='candidate')
                    async with service._apply_to_target(scope, ctx, (), ref, ()):
                        pass
            except (SnapshotCasConflict, UnknownCommitOutcome) as error:
                assert type(error) is (SnapshotCasConflict if mode == 'ok' else UnknownCommitOutcome)
            else:
                raise AssertionError('no conflict')
        assert len(captured) == 1
        trace = captured[0].trace
        assert trace.transaction_outcome is (CasTransactionOutcome.ROLLED_BACK if mode == 'ok' else CasTransactionOutcome.PENDING)
        assert trace.mismatch.expected == expected and trace.mismatch.observed == base
        assert await peer[2].read('w1') == base
        async with peer[0].conn.execute("SELECT name FROM worlds WHERE world_uid='w1'") as cursor:
            assert (await cursor.fetchone())[0] == 'w1'
        print(mode, type(captured[0]).__name__, trace.transaction_outcome.value, 'peer unchanged: PASS')
for mode in ('ok', 'before', 'after'):
    run_async(probe(mode))
