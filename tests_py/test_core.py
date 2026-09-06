import pytest

from scenelyr.core import add_edge, add_node, create_scene, remove_node, update_node
from scenelyr.models import SemanticScene
from scenelyr.store import SceneStore


def test_scene_operations_and_validation():
    scene = create_scene("test", title="Test")
    scene = add_node(scene, {"id": "a", "label": "A", "kind": "actor"})
    scene = add_node(scene, {"id": "b", "label": "B", "kind": "service"})
    scene = add_edge(scene, {"from": "a", "to": "b", "kind": "request"})
    assert scene.edges[0].id == "a__b__1"
    assert update_node(scene, "b", label="Backend").nodes[1].label == "Backend"
    assert not remove_node(scene, "a").edges
    with pytest.raises(ValueError):
        add_edge(scene, {"from": "a", "to": "missing"})


def test_example_scene_json_is_accepted():
    scene = SemanticScene.model_validate_json(open("examples/order-platform.scene.json", encoding="utf-8").read())
    assert len(scene.nodes) == 9
    assert scene.to_dict()["constraints"][0]["nodeIds"] == ["provider", "operator"]


def test_store_undo_redo_and_defensive_copy():
    store = SceneStore()
    store.create(add_node(create_scene("history"), {"id": "a", "label": "A", "kind": "service"}))
    store.mutate("history", lambda scene: update_node(scene, "a", label="B"))
    assert store.undo("history").nodes[0].label == "A"
    assert store.redo("history").nodes[0].label == "B"
