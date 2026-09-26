"""Deterministic local chat grammar and registered MCP command dispatch."""
from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass
from typing import Any

from . import mcp_server as engine
from .models import SemanticScene

HELP = ('Try: rename "Object 1" to "Customer"; add "Cache"; remove "Cache"; '
        'connect "Customer" to "Database"; reverse connection-1; '
        'reconnect connection-1 from "Customer" to "Database"; '
        'redetect; inspect; render; export svg; undo; redo; validate.')
MUTATIONS = {'rename_object', 'add_node_tool', 'remove_node_tool', 'add_relationship_tool',
             'remove_relationship_tool', 'reverse_arrow', 'reconnect_arrow', 'redetect_arrows',
             'undo_scene', 'redo_scene'}
READS = {'inspect_scene', 'render_scene'}


@dataclass
class Command:
    tool: str
    arguments: dict[str, Any]
    summary: str


def revision(scene: SemanticScene) -> str:
    return hashlib.sha256(json.dumps(scene.to_dict(), sort_keys=True).encode()).hexdigest()


def resolve(scene: SemanticScene, value: str, selected: str | None = None, edge: bool = False) -> str:
    value = value.strip().strip('"\'')
    if value.lower() in {'selected', 'selection', 'this'}:
        value = selected or ''
    items = scene.edges if edge else scene.nodes
    exact = [item for item in items if item.id == value]
    matches = exact or [item for item in items if (item.label or '').casefold() == value.casefold()]
    if len(matches) != 1:
        raise ValueError(f'Choose a unique {"connection" if edge else "object"} by its name or ID: {value!r}.')
    return matches[0].id


def parse(scene: SemanticScene, message: str, selected: str | None = None) -> Command:
    message = message.strip()
    common = {'scene_id': scene.id}
    if message.lower() in {'undo', 'redo', 'redetect', 'rerun detection', 'inspect', 'render', 'validate'}:
        tool = {'undo': 'undo_scene', 'redo': 'redo_scene', 'redetect': 'redetect_arrows',
                'rerun detection': 'redetect_arrows', 'inspect': 'inspect_scene',
                'render': 'render_scene', 'validate': 'validate'}[message.lower()]
        detail = 'Re-import the source image. This replaces manual labels and relationships; undo restores them.' if tool == 'redetect_arrows' else message.capitalize()
        return Command(tool, common, detail)
    match = re.fullmatch(r'export\s+(json|svg|html|pptx)', message, re.I)
    if match:
        return Command('export', {**common, 'kind': match[1].lower()}, f'Export {match[1].upper()}')
    try:
        words = shlex.split(message)
    except ValueError as error:
        raise ValueError('Close the quotation marks around object names.') from error
    if not words:
        raise ValueError(HELP)
    verb = words[0].lower()
    if verb == 'rename' and len(words) >= 4 and 'to' in words[2:]:
        split = words.index('to', 2)
        item = resolve(scene, ' '.join(words[1:split]), selected)
        label = ' '.join(words[split+1:]).strip()
        if not label:
            raise ValueError('Enter a new label.')
        old = next(n.label for n in scene.nodes if n.id == item)
        return Command('rename_object', {**common, 'object_id': item, 'label': label}, f'Rename “{old}” → “{label}”')
    if verb == 'add' and len(words) >= 2:
        label = ' '.join(words[1:])
        base = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')[:50] or 'object'
        item, index = base, 2
        while any(n.id == item for n in scene.nodes):
            item, index = f'{base}-{index}', index+1
        return Command('add_node_tool', {**common, 'node_id': item, 'label': label}, f'Add object “{label}”')
    if verb in {'remove', 'delete'} and len(words) >= 2:
        value = ' '.join(words[1:])
        is_edge = any(e.id == (selected if value == 'selected' else value) for e in scene.edges)
        item = resolve(scene, value, selected, edge=is_edge)
        if is_edge:
            return Command('remove_relationship_tool', {**common, 'edge_id': item}, f'Remove connection {item}; keep its objects')
        count = sum(e.from_ == item or e.to == item for e in scene.edges)
        return Command('remove_node_tool', {**common, 'node_id': item}, f'Remove {item} and {count} attached connection(s)')
    if verb == 'connect' and 'to' in words[2:]:
        split = words.index('to', 2)
        source = resolve(scene, ' '.join(words[1:split]), selected)
        target = resolve(scene, ' '.join(words[split+1:]), selected)
        if source == target:
            raise ValueError('Choose two different objects.')
        return Command('add_relationship_tool', {**common, 'from_id': source, 'to_id': target}, f'Connect {source} → {target}')
    if verb == 'reverse' and len(words) >= 2:
        item = resolve(scene, ' '.join(words[1:]), selected, edge=True)
        connection = next(e for e in scene.edges if e.id == item)
        return Command('reverse_arrow', {**common, 'edge_id': item}, f'Reverse {item}: {connection.to} → {connection.from_}')
    if verb == 'reconnect' and len(words) >= 6 and words[2].lower() == 'from' and 'to' in words[4:]:
        split = words.index('to', 4)
        item = resolve(scene, words[1], selected, edge=True)
        source = resolve(scene, ' '.join(words[3:split]), selected)
        target = resolve(scene, ' '.join(words[split+1:]), selected)
        if source == target:
            raise ValueError('Choose two different objects.')
        return Command('reconnect_arrow', {**common, 'edge_id': item, 'from_object': source, 'to_object': target}, f'Reconnect {item}: {source} → {target}')
    raise ValueError('This local command was not recognized. ' + HELP)


def execute(command: Command) -> str:
    if command.tool not in MUTATIONS | READS:
        raise ValueError('Unsupported scene command')
    return getattr(engine, command.tool)(**command.arguments)
