"""In-memory editable scene store with bounded undo/redo history."""

from collections.abc import Callable

from .models import SemanticScene


class SceneStore:
    def __init__(self, history_limit: int = 50):
        self._scenes: dict[str, SemanticScene] = {}
        self._past: dict[str, list[SemanticScene]] = {}
        self._future: dict[str, list[SemanticScene]] = {}
        self._limit = history_limit

    def create(self, scene: SemanticScene) -> SemanticScene:
        if scene.id in self._scenes:
            raise ValueError(f"Scene already exists: {scene.id}")
        self._scenes[scene.id] = scene.model_copy(deep=True)
        self._past[scene.id], self._future[scene.id] = [], []
        return self.get(scene.id)

    def get(self, scene_id: str) -> SemanticScene:
        if scene_id not in self._scenes:
            raise KeyError(f"Unknown scene: {scene_id}")
        return self._scenes[scene_id].model_copy(deep=True)

    def list(self) -> list[SemanticScene]:
        return [scene.model_copy(deep=True) for scene in self._scenes.values()]

    def mutate(self, scene_id: str, update: Callable[[SemanticScene], SemanticScene]) -> SemanticScene:
        current = self.get(scene_id)
        next_scene = update(current.model_copy(deep=True))
        if next_scene.id != scene_id:
            raise ValueError("A mutation cannot change the scene id")
        self._past[scene_id].append(current)
        self._past[scene_id] = self._past[scene_id][-self._limit :]
        self._future[scene_id] = []
        self._scenes[scene_id] = next_scene.model_copy(deep=True)
        return self.get(scene_id)

    def undo(self, scene_id: str) -> SemanticScene:
        if not self._past.get(scene_id):
            raise ValueError(f"Nothing to undo for scene: {scene_id}")
        self._future[scene_id].append(self.get(scene_id))
        self._scenes[scene_id] = self._past[scene_id].pop()
        return self.get(scene_id)

    def redo(self, scene_id: str) -> SemanticScene:
        if not self._future.get(scene_id):
            raise ValueError(f"Nothing to redo for scene: {scene_id}")
        self._past[scene_id].append(self.get(scene_id))
        self._scenes[scene_id] = self._future[scene_id].pop()
        return self.get(scene_id)

