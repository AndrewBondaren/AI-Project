"""District template `connections[]` item — tz_city_generation.md §9.5.1."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    ConnectionTypeKey,
    WorldConnectionTypeRegistry,
)
from app.dataModel.settlement.enums.districtStreetRole import DistrictStreetRole

logger = logging.getLogger(__name__)


def _engine_street_connection_type() -> ConnectionTypeKey:
    return WorldConnectionTypeRegistry.require_engine(
        WorldConnectionTypeRegistry.SYSTEM_CONNECTION_TYPE_ROAD,
    )


def _engine_alley_connection_type() -> ConnectionTypeKey:
    return WorldConnectionTypeRegistry.require_engine("alley")


# Resolved engine key — not a parallel literal. Canonical templates omit connections[].
DEFAULT_CONNECTION_TYPE = _engine_street_connection_type()


class DistrictConnection(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    connection_type: StrictOnWire[ConnectionTypeKey]
    role: DefaultOnWire[str | None] = None
    sidewalk: DefaultOnWire[bool | None] = None
    lanes_per_side: DefaultOnWire[int | None] = None

    @classmethod
    def street_default(cls) -> DistrictConnection:
        """Primary connection when template omits ``connections[]``."""
        return cls(connection_type=_engine_street_connection_type())


def parse_district_connection(raw: Any) -> DistrictConnection | None:
    if isinstance(raw, DistrictConnection):
        return raw
    if isinstance(raw, dict):
        return DistrictConnection.model_validate(raw)
    return None


def connections_from_template(template: Any) -> list[DistrictConnection]:
    raw = getattr(template, "connections", None)
    if not raw:
        return []
    out: list[DistrictConnection] = []
    for item in raw:
        parsed = item if isinstance(item, DistrictConnection) else parse_district_connection(item)
        if parsed is not None:
            out.append(parsed)
    return out


def primary_from_template(template: Any) -> DistrictConnection | None:
    """First ``connections[]`` row when present and valid."""
    rows = connections_from_template(template)
    return rows[0] if rows else None


def primary_or_default(template: Any) -> DistrictConnection:
    return primary_from_template(template) or DistrictConnection.street_default()


@dataclass(frozen=True)
class DistrictStreetClasses:
    """``connections[]`` classified by ``DistrictStreetRole`` for grid paint / frontage."""

    main: DistrictConnection | None = None
    service: DistrictConnection | None = None
    alley: DistrictConnection | None = None
    unlabeled: DistrictConnection | None = None
    skipped_roles: tuple[str, ...] = ()

    @property
    def spine(self) -> DistrictConnection:
        return (
            self.main
            or self.service
            or self.unlabeled
            or DistrictConnection.street_default()
        )

    @property
    def fill(self) -> DistrictConnection:
        if self.main is not None and self.service is not None:
            return self.service
        return self.spine


def _is_alley_type(conn: DistrictConnection) -> bool:
    return conn.connection_type == _engine_alley_connection_type()


def street_classes_for(template: Any) -> DistrictStreetClasses:
    """
    Engine roles: ``main_street`` / ``service_road`` / ``back_alley``.
    Unknown ``role`` → warning and skip that row.
    Omit role + ``connection_type=alley`` → alley class.
    Omit role + other type → unlabeled (whole-grid policy when no main/service).
    """
    main: DistrictConnection | None = None
    service: DistrictConnection | None = None
    alley: DistrictConnection | None = None
    unlabeled: DistrictConnection | None = None
    skipped: list[str] = []

    for conn in connections_from_template(template):
        raw_role = conn.role
        role = DistrictStreetRole.from_wire(raw_role)
        if raw_role is not None and str(raw_role).strip() and role is None:
            skipped.append(str(raw_role).strip())
            logger.warning(
                "DistrictConnection | unknown role %r — skip row type=%s",
                raw_role,
                conn.connection_type,
            )
            continue
        if role is DistrictStreetRole.BACK_ALLEY or (
            role is None and _is_alley_type(conn)
        ):
            if alley is None:
                alley = conn
            else:
                logger.warning(
                    "DistrictConnection | extra alley row ignored type=%s",
                    conn.connection_type,
                )
            continue
        if role is DistrictStreetRole.MAIN_STREET:
            if main is None:
                main = conn
            else:
                logger.warning("DistrictConnection | extra main_street row ignored")
            continue
        if role is DistrictStreetRole.SERVICE_ROAD:
            if service is None:
                service = conn
            else:
                logger.warning("DistrictConnection | extra service_road row ignored")
            continue
        if unlabeled is None:
            unlabeled = conn
        else:
            logger.warning(
                "DistrictConnection | extra unlabeled row ignored type=%s",
                conn.connection_type,
            )

    return DistrictStreetClasses(
        main=main,
        service=service,
        alley=alley,
        unlabeled=unlabeled,
        skipped_roles=tuple(skipped),
    )
