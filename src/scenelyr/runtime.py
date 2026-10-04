"""Locate the bundled Codex runtime across supported ChatGPT app layouts."""
from pathlib import Path


CODEX_CANDIDATES = (
    Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'),
    Path('/Applications/ChatGPT.app/Contents/Resources/codex'),
    Path.home() / 'Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex',
    Path.home() / 'Applications/ChatGPT.app/Contents/Resources/codex',
)


def find_codex() -> Path | None:
    return next((candidate for candidate in CODEX_CANDIDATES if candidate.is_file()), None)
