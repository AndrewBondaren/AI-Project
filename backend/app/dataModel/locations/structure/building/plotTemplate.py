"""Plot library body — TZ tz_domain_template_libraries.md §1–2.

Reuse the existing composition and cascade source class: a second subclass
would register duplicate channels in the global cascade graph. Member UID
is supplied separately by TemplateEntry, never inferred from DrawingKey.
"""

from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    DrawingKey,
    PlotLayoutTemplate,
)

PlotTemplate = PlotLayoutTemplate
type PlotKey = DrawingKey

__all__ = ["PlotKey", "PlotTemplate"]
