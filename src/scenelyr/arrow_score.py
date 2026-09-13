"""Small, deterministic scoring helpers for arrow extraction benchmarks."""

from __future__ import annotations

from typing import Any

from .models import SemanticScene


def score_arrows(scene: SemanticScene, expected: list[dict[str, Any]]) -> dict[str, Any]:
    """Score path, endpoints, direction, and label separately for every expected edge."""
    actual = [edge.model_dump(by_alias=True, exclude_none=True) for edge in scene.edges]
    rows = []
    for item in expected:
        same_pair = [edge for edge in actual if {edge["from"], edge["to"]} == {item["from"], item["to"]}]
        directed = [edge for edge in same_pair if edge["from"] == item["from"] and edge["to"] == item["to"]]
        label = item.get("label")
        label_match = any((edge.get("label") or "").casefold() == (label or "").casefold() for edge in directed)
        rows.append({
            "id": item["id"],
            "pathFound": bool(same_pair),
            "sourceCorrect": bool(directed),
            "destinationCorrect": bool(directed),
            "directionCorrect": bool(directed),
            "labelCorrect": label_match if label is not None else bool(directed),
        })
    fields = ("pathFound", "sourceCorrect", "destinationCorrect", "directionCorrect", "labelCorrect")
    totals = {field: sum(bool(row[field]) for row in rows) for field in fields}
    return {"expectedCount": len(expected), "detectedCount": len(actual), "totals": totals, "arrows": rows}
