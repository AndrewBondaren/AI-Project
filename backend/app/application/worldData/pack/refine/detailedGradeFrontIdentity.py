"""terrain_key / site_id / dz for one FrontGeometry — R41-T-10 / T-11.

One builder. Facade pick and ``DiscoveredFront`` read these fields; paint does not
recompute. ``site_id`` is ``PackJobUid.grade_front_site``, not a raw f-string.
Does not alias ``Coord``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.discover.plugins import (
    shore_condition_at,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    DiscoveredFront,
    FrontGeometry,
    GradePaintSpec,
    ReliefSurface,
)
from app.application.worldData.generators.terrain.relief.geom.outward import relief_dz
from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    RibbonGradeDecision,
)
from app.application.worldData.generators.terrain.relief.sample.terrainMap import (
    map_system_terrain,
)
from app.application.worldData.pack.refine.detailedJobUid import front_grade_site


@dataclass(frozen=True, slots=True)
class FrontBakeIdentity:
    """Stable pick/persist identity for one C41 front."""

    terrain_key: str
    system_terrain: str
    site_id: str
    dz: int
    owner_uid: str | None = None


def front_terrain(surface: ReliefSurface, front: FrontGeometry) -> tuple[str, str]:
    raw = (
        surface.terrain_at(front.corridor[0])
        if front.corridor
        else None
    ) or surface.terrain_at(front.rim[0]) or ""
    seed = front.corridor[0] if front.corridor else front.rim[0]
    mapped = map_system_terrain(raw)
    if mapped is not None and mapped.is_shore_class():
        return mapped.value, raw
    shore = shore_condition_at(seed, surface)
    if shore is not None and (
        mapped is None
        or surface.hydro_role_at(seed) is not None
    ):
        return shore.value, raw
    key = mapped.value if mapped is not None else raw
    return key, raw


def front_site_id(front: FrontGeometry) -> str:
    ax, ay = front.rim[0]
    return front_grade_site(
        front.context.value, ax, ay, front.outward.value,
    )


def front_bake_identity(
    surface: ReliefSurface,
    front: FrontGeometry,
    *,
    owner_uid: str | None = None,
) -> FrontBakeIdentity:
    terrain_key, system_terrain = front_terrain(surface, front)
    return FrontBakeIdentity(
        terrain_key=terrain_key,
        system_terrain=system_terrain or terrain_key,
        site_id=front_site_id(front),
        dz=relief_dz(front.z_body, front.z_end),
        owner_uid=owner_uid,
    )


def discovered_front_from(
    front: FrontGeometry,
    identity: FrontBakeIdentity,
    *,
    grade_uid: str,
    decision: RibbonGradeDecision,
    template_uid: str | None,
) -> DiscoveredFront:
    return DiscoveredFront(
        spec=GradePaintSpec(
            grade_uid=grade_uid,
            outward=front.outward,
            front_w=len(front.rim),
            anchor_top=min(front.rim),
            anchor_bottom=front.anchor_bottom,
            decision=decision,
            corridor=front.corridor,
        ),
        context=front.context,
        site_id=identity.site_id,
        slot=front.slot,
        template_uid=template_uid,
        rim=front.rim,
        terrain_key=identity.terrain_key,
        system_terrain=identity.system_terrain,
        dz=identity.dz,
        owner_uid=identity.owner_uid,
    )
