from app.dataModel.time.operations.lifecycle import BindInitialTime, RebindBranchTime
from app.dataModel.time.storage.state import TimeClockState
from app.dataModel.time.values.point import TimePoint


class TimeLifecycle:
    @staticmethod
    def bind_initial(request: BindInitialTime) -> TimeClockState:
        return TimeClockState(point=TimePoint(
            world_uid=request.world_uid, timeline_id=request.timeline_id,
            seconds=request.initial.seconds, nanoseconds=request.initial.nanoseconds,
        ))

    @staticmethod
    def rebind_branch(request: RebindBranchTime) -> TimeClockState:
        point = request.source.state.point
        return TimeClockState(point=TimePoint(
            world_uid=point.world_uid, timeline_id=request.target_timeline_id,
            seconds=point.seconds, nanoseconds=point.nanoseconds,
        ))
