"""SceneLyr's Python-first deterministic implementation."""

from .compiler import compile_scene
from .core import add_edge, add_node, create_scene, remove_node, update_node
from .models import SemanticScene
from .pixels import extract_pixels

__all__ = [
    "SemanticScene",
    "add_edge",
    "add_node",
    "compile_scene",
    "create_scene",
    "extract_pixels",
    "remove_node",
    "update_node",
]

__version__ = "0.1.0"
