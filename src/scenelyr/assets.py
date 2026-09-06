"""Small deterministic built-in asset resolver."""

from dataclasses import dataclass

from .models import SemanticNode


@dataclass(frozen=True)
class Asset:
    id: str
    label: str
    glyph: str
    keywords: tuple[str, ...]


ASSETS = (
    Asset("actor", "Person", "USR", ("customer", "user", "person", "actor")),
    Asset("app", "Application", "APP", ("app", "mobile", "client", "frontend")),
    Asset("gateway", "API Gateway", "API", ("api", "gateway", "edge")),
    Asset("service", "Service", "SVC", ("service", "worker", "backend", "microservice")),
    Asset("kafka", "Kafka", "K", ("kafka", "event bus", "stream", "queue")),
    Asset("redis", "Redis", "R", ("redis", "cache")),
    Asset("postgres", "PostgreSQL", "PG", ("postgres", "postgresql", "sql", "database")),
    Asset("database", "Database", "DB", ("database", "storage", "persistent")),
    Asset("queue", "Queue", "Q", ("queue", "async", "message", "event")),
    Asset("cache", "Cache", "C", ("cache", "memory")),
    Asset("external", "External system", "EXT", ("external", "partner", "third party")),
    Asset("image", "Image", "IMG", ("image", "visual", "photo", "asset")),
)


def search_assets(query: str, limit: int = 5) -> list[dict]:
    query = query.lower().strip()
    ranked = []
    for asset in ASSETS:
        score = 12 if asset.id == query else 0
        score += 10 if asset.label.lower() == query else 0
        score += 5 if query and query in asset.label.lower() else 0
        score += sum(8 if word == query else 3 if query and (word in query or query in word) else 0 for word in asset.keywords)
        if score:
            ranked.append((score, asset))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    return [{"id": asset.id, "label": asset.label, "glyph": asset.glyph, "source": "builtin", "score": score}
            for score, asset in ranked[:limit]]


def resolve_node_asset(node: SemanticNode) -> dict:
    for query in (node.icon, f"{node.label} {node.kind}", node.kind):
        if query and (found := search_assets(query, 1)):
            return found[0]
    return {"id": "service", "label": "Service", "glyph": "SVC", "source": "builtin", "score": 0}

