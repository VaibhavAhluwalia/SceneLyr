import { assertValidScene, cloneScene, type SemanticScene } from "../../core/src/index.js";

interface HistoryEntry {
  past: SemanticScene[];
  future: SemanticScene[];
}

export class SceneStore {
  private scenes = new Map<string, SemanticScene>();
  private history = new Map<string, HistoryEntry>();

  save(scene: SemanticScene): SemanticScene {
    assertValidScene(scene);
    const existing = this.scenes.get(scene.id);
    if (existing) this.pushPast(scene.id, existing);
    this.scenes.set(scene.id, cloneScene(scene));
    this.ensureHistory(scene.id).future = [];
    return this.get(scene.id)!;
  }

  create(scene: SemanticScene): SemanticScene {
    if (this.scenes.has(scene.id)) throw new Error(`Scene already exists: ${scene.id}`);
    assertValidScene(scene);
    this.scenes.set(scene.id, cloneScene(scene));
    this.history.set(scene.id, { past: [], future: [] });
    return this.get(scene.id)!;
  }

  get(id: string): SemanticScene | undefined {
    const scene = this.scenes.get(id);
    return scene ? cloneScene(scene) : undefined;
  }

  list(): SemanticScene[] {
    return [...this.scenes.values()].map(cloneScene);
  }

  delete(id: string): boolean {
    this.history.delete(id);
    return this.scenes.delete(id);
  }

  mutate(id: string, updater: (scene: SemanticScene) => SemanticScene): SemanticScene {
    const current = this.scenes.get(id);
    if (!current) throw new Error(`Unknown scene: ${id}`);
    const next = updater(cloneScene(current));
    if (next.id !== id) throw new Error("A scene mutation cannot change the scene id");
    assertValidScene(next);
    this.pushPast(id, current);
    this.scenes.set(id, cloneScene(next));
    this.ensureHistory(id).future = [];
    return this.get(id)!;
  }

  undo(id: string): SemanticScene {
    const current = this.scenes.get(id);
    const history = this.ensureHistory(id);
    const previous = history.past.pop();
    if (!current || !previous) throw new Error(`Nothing to undo for scene: ${id}`);
    history.future.push(cloneScene(current));
    this.scenes.set(id, cloneScene(previous));
    return this.get(id)!;
  }

  redo(id: string): SemanticScene {
    const current = this.scenes.get(id);
    const history = this.ensureHistory(id);
    const next = history.future.pop();
    if (!current || !next) throw new Error(`Nothing to redo for scene: ${id}`);
    history.past.push(cloneScene(current));
    this.scenes.set(id, cloneScene(next));
    return this.get(id)!;
  }

  private ensureHistory(id: string): HistoryEntry {
    let entry = this.history.get(id);
    if (!entry) {
      entry = { past: [], future: [] };
      this.history.set(id, entry);
    }
    return entry;
  }

  private pushPast(id: string, scene: SemanticScene): void {
    const history = this.ensureHistory(id);
    history.past.push(cloneScene(scene));
    if (history.past.length > 50) history.past.shift();
  }
}
