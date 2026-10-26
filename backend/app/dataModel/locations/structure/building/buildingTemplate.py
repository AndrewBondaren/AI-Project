"""Library building definition; parameter defaults stay on BuildingBodyTemplate.

TZ: tz_domain_template_libraries.md §1–2. Member identity is carried by
the catalog, separately from this body's readable system_name.
"""

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.locations.structure.building.buildingBodyTemplate import BuildingBodyTemplate
from app.dataModel.registryKey import RegistryKey


class BuildingTemplate(BuildingBodyTemplate):
    """Named library building; inline plot bodies do not require member metadata."""

    system_name: StrictOnWire[RegistryKey[BuildingTemplate]]
    display_name: StrictOnWire[str]


type BuildingKey = RegistryKey[BuildingTemplate]
BuildingTemplate.model_rebuild()
