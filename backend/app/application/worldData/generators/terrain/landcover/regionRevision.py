"""One revision token for collect and the baked spatial index."""

from pydantic import TypeAdapter

from app.application.worldData.generators.terrain.landcover.types import ResolvedRegion
from app.application.worldData.masks.regionRasterContext import RegionClaim
from app.ids import state_fingerprint


def region_fingerprint(region: ResolvedRegion) -> str:
    spec = (region.spec.model_copy(update={"shape": region.authored_anchor_shape})
            if region.authored_anchor_shape is not None else region.spec)
    spec_wire = spec.model_dump(mode="json")
    return state_fingerprint(spec_wire if region.claim is None else {
        "spec": spec_wire, "entry_type": region.entry_type,
        "claim": TypeAdapter(RegionClaim).dump_python(region.claim, mode="json"),
    })
