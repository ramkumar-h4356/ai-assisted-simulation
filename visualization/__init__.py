"""M12 standalone visualization dashboard generation."""

from visualization.builder import DEFAULT_POINT_LIMIT, build_visualization_bundle
from visualization.models import VisualizationBundle
from visualization.serialization import (
    VisualizationSerializationError, bundle_from_dict, bundle_to_dict,
    dumps_bundle, fingerprint_bundle, load_bundle, loads_bundle,
    render_html, save_bundle, save_html,
)

__all__ = [
    "DEFAULT_POINT_LIMIT", "VisualizationBundle", "VisualizationSerializationError",
    "build_visualization_bundle", "bundle_from_dict", "bundle_to_dict",
    "dumps_bundle", "fingerprint_bundle", "load_bundle", "loads_bundle",
    "render_html", "save_bundle", "save_html",
]
