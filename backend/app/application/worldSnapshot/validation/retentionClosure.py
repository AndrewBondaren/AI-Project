"""Pure projection of the artifacts required by one resulting snapshot."""
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.worldSnapshot.metadata.envelope import SnapshotEnvelope


def retention_closure(metadata: SnapshotEnvelope) -> tuple[ArtifactRef, ...]:
    return tuple(dict.fromkeys(artifact for entry in (*metadata.states, *metadata.history)
                               for artifact in entry.artifacts))
