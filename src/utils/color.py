from typing import Any

import seaborn as sns


def rgb_to_hex(r_value, g_value, b_value):
    r_value, g_value, b_value = int(r_value * 255), int(g_value * 255), int(b_value * 255)
    return f"#{r_value:02x}{g_value:02x}{b_value:02x}"


def get_object_type_color_map(object_types: set[Any]) -> dict[Any, Any]:
    object_type_palette = sns.color_palette("Set2", len(object_types))
    return {object_type: object_type_palette[index] for index, object_type in enumerate(object_types)}
