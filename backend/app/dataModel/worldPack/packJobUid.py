"""Pack job / grade-site uid wire — R36w, [`tz_world_pack_storage.md`](../../../docs/tz_world_pack_storage.md) job uid.

SoT for separators and site kinds. Application helpers only compose from this POJO.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class PackJobSiteKind(StrEnum):
    """Segment before ``:`` in a site token (``tile:{gx},{gy}``)."""

    TILE = "tile"
    CHUNK = "chunk"
    TILE_EDGE = "tile_edge"
    INTERIOR = "interior"
    FACE = "face"


class FaceGridAxis(StrEnum):
    """Chunk-grid face axis in ``face_key`` / ``FaceKey.axis`` (not ``Facing``)."""

    V = "V"
    H = "H"


class PackJobUid(BaseModel):
    """Wire format for L0 tile uid, detailed chunk/edge jobs, and grade sites."""

    SCHEMA_ID: ClassVar[str] = "SCH-PACK-JOB-UID"
    model_config = ConfigDict(extra="forbid", frozen=True)

    sep: str = Field(default="|", min_length=1)

    @classmethod
    def canonical_defaults(cls) -> PackJobUid:
        return cls()

    def join(self, *parts: str) -> str:
        return self.sep.join(parts)

    def coords(self, a: int, b: int) -> str:
        return f"{a},{b}"

    def kind_coords(self, kind: PackJobSiteKind, a: int, b: int) -> str:
        return f"{kind.value}:{self.coords(a, b)}"

    def tile_site(self, tile_gx: int, tile_gy: int) -> str:
        return self.kind_coords(PackJobSiteKind.TILE, tile_gx, tile_gy)

    def chunk_site(self, cx: int, cy: int) -> str:
        return self.kind_coords(PackJobSiteKind.CHUNK, cx, cy)

    def tile_uid(self, *, world_seed: str, tile_gx: int, tile_gy: int) -> str:
        return self.join(world_seed, self.tile_site(tile_gx, tile_gy))

    def chunk_uid(
        self,
        *,
        world_seed: str,
        tile_gx: int,
        tile_gy: int,
        cx: int,
        cy: int,
    ) -> str:
        return self.join(
            self.tile_uid(world_seed=world_seed, tile_gx=tile_gx, tile_gy=tile_gy),
            self.chunk_site(cx, cy),
        )

    def tile_edge_uid(
        self,
        *,
        world_seed: str,
        owner_gx: int,
        owner_gy: int,
        compact_side: str,
    ) -> str:
        return self.join(
            world_seed,
            self.kind_coords(PackJobSiteKind.TILE_EDGE, owner_gx, owner_gy),
            compact_side,
        )

    def interior_site(
        self,
        *,
        tile_gx: int,
        tile_gy: int,
        cx: int,
        cy: int,
        k: int,
    ) -> str:
        return self.join(
            self.tile_site(tile_gx, tile_gy),
            self.chunk_site(cx, cy),
            PackJobSiteKind.INTERIOR.value,
            str(k),
        )

    def face_wire(self, axis: FaceGridAxis | str, cx: int, cy: int) -> str:
        return self.join(str(axis), str(cx), str(cy))

    def face_site(self, tile_gx: int, tile_gy: int, face_wire: str) -> str:
        return self.join(
            self.tile_site(tile_gx, tile_gy),
            f"{PackJobSiteKind.FACE.value}:{face_wire}",
        )

    def grade_front_site(self, context: str, x: int, y: int, facing: str) -> str:
        """Pick/seed site for one discovered front. Same sep/coords as other sites.

        Not a new ``PackJobSiteKind`` / hash domain — compose only.
        """
        return self.join(context, self.coords(x, y), facing)
