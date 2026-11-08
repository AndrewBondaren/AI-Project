from app.application.time.calendar.projection import CalendarProjector
from app.application.time.calendar.validation import CalendarValidator
from app.application.time.changes.advancePipelineOpenPipeline import ITimeAdvancePipelineOpenPipeline, TimeAdvancePipelineOpenPipeline
from app.application.time.reads.reader import TimeReader
from app.application.time.reads.sourcePort import ITimeReadSource
from app.application.time.reads.snapshotSource import SnapshotTimeReadSource
from app.application.worldSnapshot.service.acceptedStateReader import AcceptedStateReader
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.db.repositories.sqlite.snapshotCore.history.snapshotHistoryStore import SqliteSnapshotHistoryStore
from app.db.repositories.sqlite.snapshotCore.publications.worldPublicationStore import SqliteWorldPublicationStore
from app.db.repositories.sqlite.timeStateReader import SqliteTimeStateReader


def make_time_reader(source: ITimeReadSource | SqlitePublicationCommitStore) -> TimeReader:
    if isinstance(source, SqlitePublicationCommitStore):
        access = ScopedSqliteAccess(source.registry)
        publications = SqliteWorldPublicationStore(source, access)
        history = SqliteSnapshotHistoryStore(source, access)
        return TimeReader(SnapshotTimeReadSource(source, publications, AcceptedStateReader(publications, history),
                                                 SqliteTimeStateReader(access)))
    return TimeReader(source)


def make_time_advance_pipeline() -> ITimeAdvancePipelineOpenPipeline:
    return TimeAdvancePipelineOpenPipeline()


def make_calendar_projector() -> CalendarProjector:
    return CalendarProjector()


def make_calendar_validator() -> CalendarValidator:
    return CalendarValidator()
