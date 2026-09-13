import json

from fastapi.testclient import TestClient
import cv2
import numpy as np

from scenelyr.api import app
from scenelyr.mcp_server import mcp


def test_fastapi_health_and_capabilities():
    client = TestClient(app)
    assert client.get("/health").json() == {"ok": True, "engine": "python", "deterministic": True}
    capabilities = client.get("/capabilities").json()
    assert capabilities["modelRequired"] is False


def test_no_command_ui_import_and_downloads(tmp_path, monkeypatch):
    monkeypatch.setenv("SCENELYR_DATA_DIR", str(tmp_path / "data"))
    image = np.full((240, 500, 3), 255, np.uint8)
    cv2.rectangle(image, (30, 70), (170, 170), (0, 0, 0), 2)
    cv2.rectangle(image, (330, 70), (470, 170), (0, 0, 0), 2)
    cv2.line(image, (170, 120), (330, 120), (0, 0, 0), 2)
    path = tmp_path / "flow.png"
    cv2.imwrite(str(path), image)
    client = TestClient(app)
    assert "Drop a PNG" in client.get("/").text
    with path.open("rb") as stream:
        response = client.post("/ui/import", files={"image": ("flow.png", stream, "image/png")})
    assert response.status_code == 200
    result = response.json()
    assert result["objects"] == 2 and result["connections"] == 1
    folder = tmp_path / "data" / "imports" / result["id"]
    assert {"scene.json", "preview.svg", "inspector.html", "editable.pptx"} <= {path.name for path in folder.iterdir()}
    assert len(result["nodes"]) == 2 and result["nodes"][0]["bounds"]
    manifest = json.loads((folder / "assets" / "manifest.json").read_text())
    assert manifest["root"]["id"] == result["id"]
    assert [item["id"] for item in manifest["root"]["children"]] == ["object-1", "object-2"]
    first_object = folder / "assets" / "objects" / "object-1"
    assert {"crop.png", "layer.svg", "object.json"} <= {item.name for item in first_object.iterdir()}
    record = json.loads((first_object / "object.json").read_text())
    assert record["parent"] == {"type": "scene", "id": result["id"]}
    assert record["text"]["value"] == "Object 1"
    assert record["geometry"]["sourceBounds"] == result["nodes"][0]["bounds"]
    assert record["files"]["crop"].endswith("/assets/objects/object-1/crop.png")
    assert client.get(f"/ui/scenes/{result['id']}/objects/object-1/crop").status_code == 200
    assert client.get(f"/ui/scenes/{result['id']}/objects/object-1/record").json()["id"] == "object-1"
    assert "<svg" in client.get(f"/ui/scenes/{result['id']}/objects/object-1/layer").text
    assert client.get("/ui/history").json()["imports"][0]["id"] == result["id"]
    node_id = result["nodes"][0]["id"]
    edited = client.patch(f"/ui/scenes/{result['id']}/nodes/{node_id}", json={"label": "Customer"})
    assert edited.status_code == 200 and edited.json()["nodes"][0]["label"] == "Customer"
    edited_record = json.loads((first_object / "object.json").read_text())
    assert edited_record["text"]["value"] == "Customer"
    edge_id = result["edges"][0]["id"]
    reversed_edge = client.post(f"/ui/scenes/{result['id']}/edges/{edge_id}/reverse")
    assert reversed_edge.status_code == 200
    assert reversed_edge.json()["edges"][0]["from"] == result["edges"][0]["to"]
    assert client.get(f"/ui/export/{result['id']}/json").status_code == 200
    assert client.get(f"/ui/export/{result['id']}/svg").status_code == 200
    pptx = client.get(f"/ui/export/{result['id']}/pptx")
    assert pptx.status_code == 200 and len(pptx.content) > 10_000


def test_python_mcp_registers_tools():
    tools = {tool.name: tool for tool in mcp._tool_manager.list_tools()}
    names = set(tools)
    assert {"create_scene_tool", "import_pixels", "render_scene", "export_scene",
            "rename_object", "reverse_arrow", "reconnect_arrow",
            "inspect_arrow_detection_profile", "redetect_arrows"} <= names
    override_schema = tools["redetect_arrows"].parameters["properties"]["overrides"]
    assert {item["type"] for item in override_schema["anyOf"]} == {"object", "null"}
