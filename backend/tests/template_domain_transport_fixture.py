"""Shared real-library transport graph fixture; no test discovery side effects."""
from app.ids import LibraryKind

S, B, P = LibraryKind.STRUCTURE_TEMPLATES, LibraryKind.BUILDING_TEMPLATES, LibraryKind.PLOT_TEMPLATES


async def create_graph(case, *, owner=None, name="user.transport", separate=False):
    pack = await case.service.create_pack(system_name=name, owner_world_uid=owner)
    structure = await case.service.create_member(pack.pack_uid, library_kind=S, local_uid="same",
        body={"display_name": "Geometry"}, world_uid=owner)
    bodies_pack = (await case.service.create_pack(system_name=f"{name}.bodies", owner_world_uid=owner,
        dependencies=(pack.pack_uid,)) if separate else pack)
    building = await case.service.create_member(bodies_pack.pack_uid, library_kind=B, local_uid="same",
        body={"system_name": "same", "display_name": "House", "structure": structure.template_uid,
              "foundation_depth": 0, "porch_has_roof": False}, world_uid=owner)
    plot = await case.service.create_member(bodies_pack.pack_uid, library_kind=P, local_uid="same",
        body={"system_name": "same", "display_name": "Plot", "main_building": {
            "structure": structure.template_uid, "roof_material": None},
            "secondary_buildings": [{"structure": structure.template_uid, "foundation_depth": 0}]}, world_uid=owner)
    duplicate = await case.service.copy_member(building.template_uid, bodies_pack.pack_uid, world_uid=owner)
    return pack, bodies_pack, structure, building, plot, duplicate.member
