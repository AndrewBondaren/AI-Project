"""mock-мир Lifecycle: deterministic facts, not a production world."""

from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


def mock_lifecycle_world() -> WorldPublicationRef:
    return WorldPublicationRef(
        world_uid="mock-lifecycle-world", publication_id="mock-publication-0",
        pack_hash="a" * 64, snapshot_head=None,
        active_timeline_id="mock-timeline", gameplay_started=True,
    )
