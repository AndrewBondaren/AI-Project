"""Complete wire fixtures for tests focused on an individual template field."""


def room_wire(**fields):
    return dict(room_id="hall", display_name="Hall", room_type="common_hall",
                is_public=True, is_forbidden=False, required=True,
                shape_type="rectangle", size={"width_range": [5, 5], "depth_range": [5, 5]}) | fields


def level_wire(**fields):
    return dict(z_offset=0, display_name="Ground", rooms=[room_wire()]) | fields
