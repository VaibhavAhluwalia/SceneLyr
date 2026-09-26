"""Optional per-call observation; never changes deterministic extraction results."""
from contextvars import ContextVar
from typing import Callable

observer: ContextVar[Callable[[dict], None] | None] = ContextVar('import_observer', default=None)


def report(stage: str, state: str, **details) -> None:
    callback = observer.get()
    if callback:
        callback({'stage': stage, 'state': state, **details})
