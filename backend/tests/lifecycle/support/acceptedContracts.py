"""Closed runtime lookup models, separate from current captures and wire data."""
from app.dataModel.lifecycle.storage.acceptedChanges import AcceptedChangeAbsent, AcceptedChangeFound, AcceptedChangesResult
from tests.lifecycle.support import mixedContracts as m

TransitionAB = (m.CreateTransitionA | m.ReplaceTransitionA | m.EndTransitionA | m.ReactivateTransitionA
                | m.CreateTransitionB | m.ReplaceTransitionB | m.EndTransitionB | m.ReactivateTransitionB)


class AcceptedChangeFoundAB(AcceptedChangeFound[TransitionAB]):
    pass


AcceptedEntryAB = AcceptedChangeAbsent | AcceptedChangeFoundAB


class AcceptedChangesResultAB(AcceptedChangesResult[AcceptedEntryAB]):
    pass
