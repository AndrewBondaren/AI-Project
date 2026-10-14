"""Plot library body row; ownership stays in library_pack_members/packs.

TZ: tz_domain_template_libraries.md §3; metadata is separate from the POJO.
"""

from dataclasses import dataclass

from app.db.mapper import json_col


@dataclass
class PlotTemplateRow:
    __table__ = "plot_templates"
    __pk__ = "template_uid"

    template_uid: str
    system_name: str
    display_name: str
    data: dict = json_col(default_factory=dict)
    source_file: str | None = None
